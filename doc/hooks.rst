=====
Hooks
=====

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
a Click package, and one which is simple but not too simple.
unity-scope-manpages (ignoring its dependencies) delivers a plugin for the
unity help lens (/usr/share/unity/lenses/help/unity-scope-manpages.scope)
and a D-Bus service
(/usr/share/dbus-1/services/unity-scope-manpages.service).  These are
consumed by unity-lens-help and dbus respectively, and each lists the
corresponding directory looking for files to consume.

We must assume that in the general case it will be at least inconvenient to
cause the integrated-with packages to look in multiple directories,
especially when the list of possible directories is not fixed, so we need a
way to cause files to exist in those directories.  On the other hand, we
cannot unpack directly into those directories, because that takes us back to
using dpkg itself.

What we can do with reasonable safety is populate symlink farms.  As a
strawman proposal, consider the following:

 * An integrated-with system package may add ``*.hook`` files to
   /usr/share/click-package/hooks/.  These are standard Debian-style control
   files with the following keys:

     Hook: <name>               (required)
     Pattern: <file-pattern>    (required)
     Exec: <program>            (optional)
     Trigger: yes               (optional)

   The value of Hook provides a name for use in the Click package manifest
   (see below).

   The value of Pattern is a printf format string which must contain exactly
   one %s substitution: the package manager substitutes an identifier
   provided by the Click package into it and creates the resulting path as a
   symlink to a path provided by the Click package.

   If the Exec key is present, its value is executed as if passed to the
   shell after the above symlink is created.

   For the optional Trigger key, see below.

 * A Click package may include a "hooks" entry in its manifest (exact format
   TBD).  If present, it must contain a mapping of keys to values.  The keys
   are used to look up ``*.hook`` files with an equal Hook field (see above).
   The values are symlink target paths used by the package manager when
   creating symlinks according to the Pattern field in ``*.hook`` files.

 * There should be a dh_clickpackage which installs the ``*.hook`` files in
   system packages and adds maintainer script fragments to cause
   click-package to catch up with any newly-provided hooks.

 * It will often be valuable to execute a dpkg trigger after installing a
   Click package to avoid code duplication between system and Click package
   handling, although we must do so asynchronously and any errors must not
   block the installation of Click packages.  If "Trigger: yes" is set in a
   ``*.hook`` file, then click-install will activate an asynchronous D-Bus
   service at the end of installation, passing the names of all the changed
   paths resulting from Pattern key expansions; this will activate any file
   triggers matching those paths, and process all the packages that enter
   the triggers-pending state as a result.

Thus, a worked example would have::

  /usr/share/click-package/hooks/unity-lens-help.hook
    Hook: unity-lens-help
    Pattern: /usr/share/unity/lenses/help/click-%s.scope
    # unity-lens-help-update is fictional, shown for the sake of exposition
    Exec: unity-lens-help-update

  /usr/share/click-package/hooks/dbus-service.hook
    Hook: dbus-service
    Pattern: /usr/share/dbus-1/services/click-%s.service

  unity-scope-manpages/manifest.json:
    "hooks": {
        "unity-lens-help": "help/unity-scope-manpages.scope",
        "dbus-service": "services/unity-scope-manpages.service",
    }

TODO: fill in details of upgrade and removal

TODO: copy rather than symlink, for additional robustness?

TODO: D-Bus services are an awkward case because they contain a full path in
the Exec line; this will probably require some kind of declarative
substitution capability too

TODO: use UUIDs instead of Click package names so that we never have to
worry about conflicts, renaming, etc.?
