=====
To do
=====

 * hook that gets notified about all installations

 * dbus interface etc. as backend for UI

   * method may not be feasible because caller may want to go away

   * but where do we send a completion/failure signal back to?

 * support for installing some apps to phone memory and some to an SD card

   * multiple installation root directories so that some apps can be
     "system" and some "user"

 * some way to manage shared data files

 * association with developer ID, to allow sharing of data

 * debug symbols

 * manual page

 * define exit statuses for "click install"

Delta updates
=============

It would be helpful to have some kind of delta update format.

Tools such as ``rsync`` and ``zsync`` are probably the wrong answer.
There's no particular reason to keep the .click file around as an rsync
target, particularly since the unpacked application directory is kept
pristine, and many devices won't have the kind of disk space where you want
to keep 4.2GB files around just for the sake of it.

We could do something ad-hoc with ``xdelta`` or ``bsdiff`` or whatever.

`debdelta <http://debdelta.debian.net/>`_ seems like a good possibility.
We're already using the .deb format, and debdelta is capable of doing patch
upgrades without having the old .deb around (though it will need minor
adjustments to cope with the different installation location of Click
packages).  Under the hood, it uses xdelta/bsdiff/etc. and can be extended
with other backends if need be.  If we used this then we could take
advantage of a good deal of existing code.
