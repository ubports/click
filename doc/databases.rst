=========
Databases
=========

(This is a lightly-edited copy of a brain-dump sent by Colin Watson to the
ubuntu-phone mailing list, preserved here since it may be useful.)

Click has multiple databases where packages may be unpacked: by default we
have the "core" database for core apps (``/usr/share/click/preinstalled/``),
the "custom" database for carrier/OEM customisations (``/custom/click/``),
and the "default" database for user-installed applications
(``/opt/click.ubuntu.com/``), although these are configurable in
``/etc/click/databases/``.  Each database may have multiple unpacked
versions of any given package.

Each database may also have user registrations, which live in
``.click/users/`` relative to the database root.  Each user has a
subdirectory of that, which contains symlinks to the versions of each
package they have registered.  This means that on a tablet, say, I can
install an app without it also showing up on my children's accounts; they'd
need to install it separately, although the disk space for the unpacked copy
of the app would be shared.

There was an idea early on that we'd deal with preinstalled apps by going
round and registering them all for all active users on first boot.  This
would have lots of problems for the packaging system, though.  Most notably,
doing it that way makes it hard for a user to remove an app and make it
stick, because it would tend to reappear on system updates.  You can
probably fudge your way around this somehow, but it gets very fiddly and
easy to get wrong.

What we do instead is: we have an ``@all`` pseudo-user which you can
register packages for, typically in the core database (``click register
--root=/usr/share/click/preinstalled --all-users``).  If a user wants to
remove a package, we do this by creating a deliberately broken symlink
pointing to ``@hidden`` in their user registration area in
``/opt/click.ubuntu.com/.click/users/$USERNAME/``.  When click is asked to
list the set of packages for a given user, it walks its way down the list of
databases from top (default) to bottom (core).  For each database, it checks
registrations for that user, followed by registrations for ``@all``.  It
takes the first registration for any given package name that it finds.  If
that registration is ``@hidden``, then it ignores the package, otherwise it
must be a link to the unpacked copy of the appropriate version of the
package.

There are still some things that can't be done just with static files in the
image and instead have to be done at boot time and on session startup: we
have to make sure the right AppArmor profiles are loaded, do things to the
user's home directory like creating .desktop files, and that kind of thing.
We run ``click hook run-system`` at boot time and ``click hook run-user`` on
session startup, and these deal with running hooks for whatever packages are
visible in context, according to the rules above.

The effect of all this is that we can hide a core app for a carrier by doing
this as root when preparing their custom overlay image::

  click unregister --root=/custom/click --all-users PACKAGE-NAME

This will create a symlink ``/custom/click/.click/users/@all/PACKAGE-NAME``
pointing to ``@hidden``.  Unless a user explicitly installs the app in
question, the effect of this will be that it's as if the app just isn't
there.  It shouldn't incur any more than a negligible cost at startup
(basically just a readlink call); at the moment I think we might still
create an AppArmor profile for it, which isn't free, but that can be fixed
easily enough.
