========================================
"Click" package file format, version 0.4
========================================

This specification covers a packaging format intended for use by
self-contained third-party applications.  It is intentionally designed to
make it easy to create such packages and for the archive of packages to be
able to scale to very large numbers, as well as to ensure that packages do
not execute any unverified code as root during installation and that
installed packages are sandboxable.

This implementation proposal uses the existing dpkg as its core, although
that is entirely concealed from both users and application developers.  The
author believes that using something based on dpkg will allow us to reuse
substantial amounts of package-management-related code elsewhere, not least
the many years of careful design and bug-fixing of dpkg itself; although
there are clearly several things we need to adjust.

General format
==============

The top-level binary format for Click packages is an ar archive containing
control and data tar archives, as for .deb packages: see deb(5) for full
details.

The deb(5) format permits the insertion of underscore-prefixed ar members,
so a "_click-binary" member should be inserted immediately after
"debian-binary"; its contents should be the current version number of this
specification followed by a newline.  This makes it possible to assign a
MIME type to Click packages without having to rely solely on their
extension.

Despite the similar format, the file extension for these packages is .click,
to discourage attempts to install using dpkg directly (although it is still
possible to use dpkg to inspect these files).  Click packages should not be
thought of as .deb packages, although they share tooling.  Do not rely on
the file extension remaining .click; it may change in the future.

Control area
============

control
-------

Every Click package must include the following control fields:

 * Click-Version: the current version number of this specification

The package manager must refuse to process packages where any of these
fields are missing or unparseable.  It must refuse to process packages where
Click-Version compares newer than the corresponding version it implements
(according to rules equivalent to "dpkg --compare-versions").  It may refuse
to process packages whose Click-Version field has an older major number than
the version it implements (although future developers are encouraged to
maintain the maximum possible degree of compatibility with packages in the
wild).

Several other fields are copied from the manifest, to ease interoperation
with Debian package manipulation tools.  The manifest is the primary
location for these fields, and Click-aware tools must not rely on their
presence in the control file.

All dependency relations are forbidden.  Packages implicitly depend on the
entire contents of the Click system framework they declare.

manifest
--------

There must be a "manifest" file in the control area (typically corresponding
to "manifest.json" in source trees), which must be a dictionary represented
as UTF-8-encoded JSON.  It must include the following keys:

 * name: unique name for the application

 * version: version number of the application

 * framework: the system framework(s) for which the package was built

 * installed-size: the size of the unpacked package in KiB; this should not
   be set directly in the source tree, but will be generated automatically
   by "click build" using "du -k -s --apparent-size"

The package manager must refuse to process packages where any of these
fields are missing or unparseable.  It must refuse to process packages where
the value of "framework" does not declare a framework implemented by the
system on which the package is being installed.

The value of "name" identifies the application, following Debian source
package name rules; every package in the app store has a unique "name"
identifier, and the app store will reject clashes.  It is the developer's
responsibility to choose a unique identifier.  The recommended approach is
to follow the Java package name convention, i.e.  "com.mydomain.myapp",
starting with the reverse of an Internet domain name owned by the person or
organisation developing the application; note that it is not necessary for
the application to contain any Java code in order to use this convention.

The value of "version" provides a unique version for the application,
following Debian version numbering rules. See deb-version(5) for full
details.

The syntax of "framework" is formally that of a Debian dependency
relationship field.  Currently, only a simple name is permitted, e.g.
"framework": "ubuntu-sdk-13.10", or a list of simple names all of which must
be satisfied, e.g. "framework": "ubuntu-sdk-14.04-qml,
ubuntu-sdk-14.04-webapps"; version relationships and alternative
dependencies are not currently allowed.

The manifest may contain arbitrary additional optional keys; new optional
keys may be defined without changing the version number of this
specification.  The following are currently recognised:

 * title: short (one-line) synopsis of the application

 * description: extended description of the application; may be
   multi-paragraph

 * maintainer: name and email address of maintainer of the application

 * architecture: one of the following:

   * "all", indicating a package containing no compiled code

   * a dpkg architecture name (e.g. "armhf") as a string, indicating a
     package that will only run on that architecture

   * a list of dpkg architecture names, indicating a package that will run
     on any of those architectures

 * hooks: see :doc:`hooks`

 * icon: icon to display in interfaces listing click packages; if the name
   refers to an existing file when resolved relative to the base directory
   of the package, the given file will be used; if not, the algorithm
   described in the `Icon Theme Specification
   <http://freedesktop.org/wiki/Specifications/icon-theme-spec/>`_ will be
   used to locate the icon

Keys beginning with the two characters "x-" are reserved for local
extensions: this file format will never define such keys to have any
particular meaning.

Keys beginning with an underscore ("_") are reserved for use as dynamic
properties of installed packages.  They must not appear in packages'
manifest files, and attempts to set them there will be ignored.  The
following dynamic keys are currently defined:

 * _directory: the directory where a package is unpacked

 * _removable: 1 if a package is unpacked in a location from which it can be
   removed, otherwise 0 (this may be changed to a proper boolean in future;
   client code should be careful to permit either)

Maintainer scripts
------------------

Maintainer scripts are forbidden, with one exception: see below.  (If they
are permitted in future, they will at most be required to consist only of
verified debhelper-generated fragments that can be statically analysed.)
Packages in Click system frameworks are encouraged to provide file triggers
where appropriate (e.g. "interest /usr/share/facility"); these will be
processed as normal for dpkg file triggers.

The exception to maintainer scripts being forbidden is that a Click package
may contain a preinst script with the effect of causing direct calls to dpkg
to refuse to install it.  The package manager must enforce the permitted
text of this script.


Data area
=========

Unlike .debs, each package installs in a self-contained directory, and the
filesystem tarball must be based at the root of that directory.  The package
must not assume any particular installation directory: if it needs to know
where it is installed, it should look at argv[0] or similar.

Within each package installation directory, the ".click" subdirectory will
be used for metadata.  This directory must not be present at the top level
of package filesystem tarballs; the package manager should silently filter
it out if present.  (Rationale: scanning the filesystem tarball in advance
is likely to impose a performance cost, especially for large packages.)

The package manager should ensure that all unpacked files and directories
are group- and world-readable, and (if owner-executable) also group- and
world-executable.  (Rationale: since packages are unpacked as a dedicated
user not used when running applications, and since packages cannot write to
their own unpack directories, any files that aren't world-readable are
unusable.)
