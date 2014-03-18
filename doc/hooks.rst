=====
Hooks
=====

Rationale
---------

Of course, any sensible packaging format needs a hook mechanism of some
kind; just unpacking a filesystem tarball isn't going to cut it.  But part
of the point of Click packages is to make packages easier to audit by
removing their ability to run code at installation time.  How do we resolve
this?  For most application packages, the code that needs to be run is to
integrate with some system package; for instance, a package that provides an
icon may need to update icon caches.  Thus, the best way to achieve both
these goals at once is to make sure the code for this is always in the
integrated-with package.

dpkg triggers are useful prior art for this approach.  In general they get a
lot of things right.  The code to process a trigger runs in the postinst,
which encourages an approach where trigger processing is a subset of full
package configuration and shares code with it.  Furthermore, the express
inability to pass any user data through the trigger activation mechanism
itself ensures that triggers must operate in a "catch up" style, ensuring
that whatever data store they manage is up to date with the state of the
parts of the file system they use as input.  This naturally results in a
system where the user can install integrating and integrated-with packages
in either order and get the same result, a valuable property which
developers are nevertheless unlikely to test explicitly in every case and
which must therefore be encouraged by design.

There are two principal problems with dpkg triggers (aside from the point
that not all integrated-with packages use them, which is irrelevant because
they don't support any hypothetical future hook mechanisms either).  The
first is that the inability to pass user data through trigger activation
means that there is no way to indicate where an integrating package is
installed, which matters when the hook files it provides cannot be in a
single location under /usr/ but might be under /opt/ or even in per-user
directories.  The second is that processing dpkg triggers requires operating
on the system dpkg database, which is large and therefore slow.

Let us consider an example of the sort that might in future be delivered as
a Click package, and one which is simple but not too simple.  Our example
package (com.ubuntu.example) delivers an AppArmor profile and two .desktop
files.  These are consumed by apparmor and desktop-integration (TBD)
respectively, and each lists the corresponding directory looking for files
to consume.

We must assume that in the general case it will be at least inconvenient to
cause the integrated-with packages to look in multiple directories,
especially when the list of possible directories is not fixed, so we need a
way to cause files to exist in those directories.  On the other hand, we
cannot unpack directly into those directories, because that takes us back to
using dpkg itself, and is incompatible with system image updates where the
root file system is read-only.  What we can do with reasonable safety is
populate symlink farms.

Specification
-------------

 * Only system packages (i.e. .debs) may declare hooks.  Click packages must
   be declarative in that they may not include code executed outside
   AppArmor confinement, which precludes declaring hooks.

 * "System-level hooks" are those which operate on the full set of installed
   package/version combinations.  They may run as any (system) user.
   (Example: AppArmor profile handling.)

 * "User-level hooks" are those which operate on the set of packages
   registered by a given user.  They run as that user, and thus would
   generally be expected to keep their state in the user's home directory or
   some similar user-owned file system location.  (Example: desktop file
   handling.)

 * System-level and user-level hooks share a namespace.

 * A Click package may contain one or more applications (the common case
   will be only one).  Each application has a name.

 * An "application ID" is a string unique to each application instance: it
   is made up of the Click package name, the application name (must consist
   only of characters for a Debian source package name, Debian version and
   [A-Z]), and the Click package version joined by underscores, e.g.
   ``com.ubuntu.clock_alarm_0.1``.

 * A "short application ID" is a string unique to each application, but not
   necessarily to each instance of it: it is made up of the Click package
   name and the application name (must consist only of characters for a Debian
   source package name, Debian version and [A-Z]) joined by an underscore,
   e.g. ``com.ubuntu.clock_alarm``.  It is only valid in user-level hooks,
   or in system-level hooks with ``Single-Version: yes``.

 * An integrated-with system package may add ``*.hook`` files to
   ``/usr/share/click/hooks/``.  These are standard Debian-style control
   files with the following keys:

   User-Level: yes (optional)
     If the ``User-Level`` key is present with the value ``yes``, the hook
     is a user-level hook.

   Pattern: <file-pattern> (required)
     The value of ``Pattern`` is a string containing one or more
     substitution placeholders, as follows:

     ``${id}``
       The application ID.

     ``${short-id}``
       The short application ID (user-level or single-version hooks only).

     ``${user}``
       The user name (user-level hooks only).

     ``${home}``
       The user's home directory (user-level hooks only).

     ``$$``
       The character '``$``'.

     At least one ``${id}`` or ``${short-id}`` substitution is required.
     For user-level hooks, at least one of ``${user}`` and ``${home}`` must
     be present.

     On install, the package manager creates the target path as a symlink to
     a path provided by the Click package; on upgrade, it changes the target
     path to be a symlink to the path in the new version of the Click
     package; on removal, it unlinks the target path.

     The terms "install", "upgrade", and "removal" are taken to refer to the
     status of the hook rather than of the package.  That is, when upgrading
     between two versions of a package, if the old version uses a given hook
     but the new version does not, then that is a removal; if the old
     version does not use a given hook but the new version does, then that
     is an install; if both versions use a given hook, then that is an
     upgrade.

     For system-level hooks, one target path exists for each unpacked
     version, unless "``Single-Version: yes``" is used (see below).  For
     user-level hooks, a target path exists only for the current version
     registered by each user for each package.

     Upgrades of user-level hooks may leave the symlink pointed at the same
     target (since the target will itself be via a ``current`` symlink in
     the user registration directory).  ``Exec`` commands in hooks should
     take care to check the modification timestamp of the target.

   Exec: <program> (optional)
     If the ``Exec`` key is present, its value is executed as if passed to
     the shell after the above symlink is modified.  A non-zero exit status
     is an error; hook implementors must be careful to make commands in
     ``Exec`` fields robust.  Note that this command intentionally takes no
     arguments, and will be run on install, upgrade, and removal; it must be
     written such that it causes the system to catch up with the current
     state of all installed hooks.  ``Exec`` commands must be idempotent.

   Trigger: yes (optional)
     It will often be valuable to execute a dpkg trigger after installing a
     Click package to avoid code duplication between system and Click
     package handling, although we must do so asynchronously and any errors
     must not block the installation of Click packages.  If "``Trigger:
     yes``" is set in a ``*.hook`` file, then "``click install``" will
     activate an asynchronous D-Bus service at the end of installation,
     passing the names of all the changed paths resulting from Pattern key
     expansions; this will activate any file triggers matching those paths,
     and process all the packages that enter the triggers-pending state as a
     result.

   User: <username> (required, system-level hooks only)
     System-level hooks are run as the user whose name is specified as the
     value of ``User``.  There is intentionally no default for this key, to
     encourage hook authors to run their hooks with the least appropriate
     privilege.

   Single-Version: yes (optional, system-level hooks only)
     By default, system-level hooks support multiple versions of packages,
     so target paths may exist at multiple versions.  "``Single-Version:
     yes``" causes only the current version of each package to have a target
     path.

   Hook-Name: <name> (optional)
     The value of ``Hook-Name`` is the name that Click packages may use to
     attach to this hook.  By default, this is the base name of the
     ``*.hook`` file, with the ``.hook`` extension removed.

     Multiple hooks may use the same hook-name, in which case all those
     hooks will be run when installing, upgrading, or removing a Click
     package that attaches to that name.

 * A Click package may attach to zero or more hooks, by including a "hooks"
   entry in its manifest.  If present, this must be a dictionary mapping
   application names to hook sets; each hook set is itself a dictionary
   mapping hook names to paths.  The hook names are used to look up
   ``*.hook`` files with matching hook-names (see ``Hook-Name`` above).  The
   paths are relative to the directory where the Click package is unpacked,
   and are used as symlink targets by the package manager when creating
   symlinks according to the ``Pattern`` field in ``*.hook`` files.

 * There is a dh_click program which installs the ``*.hook`` files in system
   packages and adds maintainer script fragments to cause click to catch up
   with any newly-provided hooks.  It may be invoked using ``dh $@ --with
   click``.

Examples
--------

::

  /usr/share/click/hooks/apparmor.hook:
    Pattern: /var/lib/apparmor/clicks/${id}.json
    Exec: /usr/bin/aa-clickhook
    User: root

  /usr/share/click/hooks/click-desktop.hook:
    User-Level: yes
    Pattern: /opt/click.ubuntu.com/.click/desktop-files/${user}_${id}.desktop
    Exec: click desktophook
    Hook-Name: desktop

  com.ubuntu.example/manifest.json:
    "hooks": {
      "example-app": {
        "apparmor": "apparmor/example-app.json",
        "desktop": "example-app.desktop"
      }
    }

TODO: copy rather than symlink, for additional robustness?
