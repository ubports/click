=====
click
=====

SYNOPSIS
========

click command [options] [arguments]

DESCRIPTION
===========

*Click* is a packaging format for Ubuntu Touch applications, independent of
the packaging format used to deliver the underlying system.  The *click*
program is the basic tool used to build, install, remove, and otherwise
manipulate these packages.

*click*'s various functions are available via a number of commands,
described in detail below.

While *click* supports per-user installation, packages are normally unpacked
as a special ``clickpkg`` user, to ensure that applications cannot modify
their own code; it is a design goal to ensure that *click* can be used to
install untrusted code which is then confined using `AppArmor
<https://wiki.ubuntu.com/AppArmor>`_.  As such, *click* should normally be
run as root (e.g. using ``sudo``) when installing packages; it will drop
privileges as needed.

COMMAND OVERVIEW
================

::

    click build DIRECTORY
    click buildsource DIRECTORY
    click contents PATH
    click hook install HOOK
    click hook remove HOOK
    click hook run-system
    click hook run-user
    click info PATH
    click install PACKAGE-FILE
    click list
    click pkgdir {PACKAGE-NAME|PATH}
    click register PACKAGE-NAME VERSION
    click unregister PACKAGE-NAME [VERSION]
    click verify PACKAGE-FILE

COMMANDS
========

click build DIRECTORY
---------------------

Build a Click package from the contents of DIRECTORY.  The build directory
must contain a JSON-formatted manifest, described further in Click's
file-format documentation; by default, this is expected to be in
``manifest.json`` at the top level of the build directory.

The resulting ``.click`` file is written to the current directory, so to
avoid confusion you should generally ensure that your working directory is
not inside the build directory when running this command.

While it is possible to build a new version of a Click package by unpacking
and repacking an existing package, this is not normally recommended because
it requires some care to put the manifest file back in the right place.  It
is best to keep your application's code in separate revision control rather
than relying on recovering it from packages.

Options:

-m PATH, --manifest=PATH    Read package manifest from PATH
                            (default: ``manifest.json``).

click buildsource DIRECTORY
---------------------------

Build a source package in ``.tar.gz`` format from the contents of DIRECTORY.
This allows you to distribute source code in the case where your package
contains compiled code (and so the Click package does not constitute its own
source).

The resulting ``.tar.gz`` file is written to the current directory, so to
avoid confusion you should generally ensure that your working directory is
not inside the build directory when running this command.

Options:

-m PATH, --manifest=PATH    Read package manifest from PATH
                            (default: ``manifest.json``).

click contents PATH
-------------------

Display the contents of the Click package in PATH as a file listing.

click hook install HOOK
-----------------------

Install files associated with HOOK for any Click packages that attach to it.

This is normally only called by maintainer scripts of system packages, by
way of dh_click(1).

Options:

--root=PATH                 Look for additional packages in PATH.

click hook remove HOOK
----------------------

Remove files associated with HOOK for any Click packages that attach to it.

This is normally only called by maintainer scripts of system packages, by
way of dh_click(1).

Options:

--root=PATH                 Look for additional packages in PATH.

click hook run-system
-------------------------

Run all system-level hooks for all installed Click packages.  This is useful
when starting up from images with preinstalled packages which may not have
had their system-level hooks run properly when building the image.

Options:

--root=PATH                 Look for additional packages in PATH.

click hook run-user
-----------------------

Run all user-level hooks for all Click packages registered for a given user.
This is useful at session startup to catch up with packages that may have
been preinstalled and registered for all users.

Options:

--root=PATH                 Look for additional packages in PATH.
--user=USER                 Run user-level hooks for USER (default: current
                            user).

click info PATH
---------------

Display the manifest for the Click package in PATH.

click install PACKAGE-FILE
--------------------------

Install the Click package in PACKAGE-FILE.

This is a low-level tool; to install a package as an ordinary user you
should generally use ``pkcon install-local PACKAGE-FILE`` or some
higher-level user interface instead, which take care to use the correct set
of options.  (Do not use ``sudo`` when invoking ``pkcon``, as it needs to
know the calling user.)

``click install`` may be used to preinstall a package in an image such that
it will be available to all users by default.  When doing this, you should
normally install it to one of the databases defined in
``/etc/click/databases/`` other than the default of
``/opt/click.ubuntu.com``.  For example:

    sudo click install --root=/custom/click --all-users foo.click

The ``--force-missing-framework`` option is necessary while working with
development versions of SDKs which have not yet put a framework declaration
in place.

Options:

--root=PATH                 Install packages underneath PATH.
--force-missing-framework   Install despite missing system framework.
--user=USER                 Register package for USER.
--all-users                 Register package for all users.

click list
----------

Display a list of installed packages, either as one package per line with
each line containing a package name and version separated by a tab (the
default), or as a JSON array of manifests.

By default, ``click list`` shows only packages registered for the current
user.  The ``--all`` option causes it to show all installed packages,
regardless of user registrations.

Options:

--root=PATH                 Look for additional packages in PATH.
--all                       List all installed packages.
--user=USER                 List packages registered by USER (if you have
                            permission).
--manifest                  Format output as a JSON array of manifests.

click pkgdir {PACKAGE-NAME|PATH}
--------------------------------

When given a package name (that is, a string containing no ``/``
characters), display the directory where that package is installed, if it is
registered for the current user.

When given a path (that is, a string containing at least one ``/``
character), attempt to treat that as a path to a file within a Click package
and print the top-level directory where that package is installed, if one
exists.  This is particularly useful in hooks that need to find the
top-level package directory based on a symbolic link to a single file within
it.

Exits zero if and only if a directory for the given package name or path was
found.

Options:

--root=PATH                 Look for additional packages in PATH.
--user=USER                 List packages registered by USER (if you have
                            permission).

click register PACKAGE-NAME VERSION
-----------------------------------

Register an installed Click package for a user.  This will normally cause
user-level hooks to be run for that user, which are needed for things such
as making the application's ``.desktop`` file available to the user
interface.

Options:

--root=PATH                 Look for additional packages in PATH.
--user=USER                 Register package for USER (default: current
                            user).
--all-users                 Register package for all users.

click unregister PACKAGE-NAME [VERSION]
---------------------------------------

Unregister an installed Click package for a user, and remove it entirely if
no other users still have it registered and if it does not appear to be
running.  This will normally cause user-level hooks to be run for that user,
which are needed for things such as removing the application's ``.desktop``
file from the user interface.

If a version is specified, then the registered version must match it in
order to be removed.

Options:

--root=PATH                 Look for additional packages in PATH.
--user=USER                 Unregister package for USER (default:
                            ``$SUDO_USER``, if known).
--all-users                 Unregister package that was previously
                            registered for all users.

click verify PACKAGE-FILE
-------------------------

Verify the Click package in PACKAGE-FILE.

The ``--force-missing-framework`` option is necessary while working with
development versions of SDKs which have not yet put a framework declaration
in place.

Options:

--root=PATH                 Install packages underneath PATH.
--force-missing-framework   Install despite missing system framework.
