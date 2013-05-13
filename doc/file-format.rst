========================================
"Click" package file format, version 0.1
========================================

This specification covers a packaging format intended for use by
self-contained third-party applications.  It is intentionally designed to be
easy to create such packages and for the archive of packages to be able to
scale to very large numbers, as well as to ensure that packages do not
execute any unverified code as root during installation and that installed
packages are sandboxable.

This implementation proposal uses the existing dpkg as its core, although
that is entirely concealed from both users and application developers.  It
is currently intended only to demonstrate that the general goals of Click
packages are achievable using a set of fairly minor modifications to dpkg.
The author believes that using something based on dpkg will allow us to
reuse substantial amounts of package-management-related code elsewhere, not
least the many years of careful design and bug-fixing of dpkg itself;
although there are clearly several things we need to adjust.

General format
==============

The top-level binary format for Click packages is an ar archive containing
control and data tar archives, as for .deb packages: see deb(5) for full
details.

Despite the similar format, the file extension for these packages is .click,
to discourage attempts to install using dpkg directly (although it is still
possible to use dpkg to inspect these files).  Click packages should not be
thought of as .deb packages, although they share tooling.  Do not rely on
the file extension remaining .click; it may change in the future.

Control area
============

Every Click package must include the following control fields:

 * Package: unique name for the application
 * Click-Version: the current version number of this specification
 * Click-Framework: the current version number of the base system

The package manager must refuse to process packages where any of these
fields are missing or unparseable.  It must refuse to process packages where
either Click-Version or Click-Framework compares newer than the
corresponding version it implements (according to rules equivalent to "dpkg
--compare-versions").  It may refuse to process packages whose Click-Version
field has an older major number than the version it implements (although
future developers are encouraged to maintain the maximum possible degree of
compatibility with packages in the wild).  It may refuse to process packages
whose Click-Framework field is older than the version it implements,
depending on library compatibility decisions made by the maintainers of that
base system.

The Package field identifies the application; every package in the app store
has a unique Package identifier, and the app store will reject clashes.  It
is the developer's responsibility to choose a unique identifier.  The
recommended approach is to follow the Java package name convention, i.e.
"com.mydomain.myapp", starting with the reverse of an Internet domain name
owned by the person or organisation developing the application; note that it
is not necessary for the application to contain any Java code in order to
use this convention.

All dependency relations are forbidden.  Packages implicitly depend on the
entire contents of the Click base system, managed elsewhere.

Maintainer scripts are forbidden, with one exception: see below.  (If they
are permitted in future, they will at most be required to consist only of
verified debhelper-generated fragments that can be statically analysed.)
Packages in the Click base system are encouraged to provide file triggers
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
