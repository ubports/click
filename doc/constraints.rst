==================
Design constraints
==================

Building packages
=================

 * Building packages should not require any more than the Python standard
   library.  In particular, it should not require dpkg, python-debian, or any
   other such Debian-specific tools.

   Rationale: We want people to be able to build Click packages easily on any
   platform (or at least any platform that can manage a Python installation,
   which is not too onerous a requirement).


Installing packages
===================

 * For the purpose of rapid prototyping, package installation is also
   implemented in Python.  This may of course use Debian/Ubuntu-specific
   tools, since it will always be running on an Ubuntu system.  In future, it
   will probably be re-implemented in C for performance.

 * Reading the system dpkg database is forbidden.  This is partly to ensure
   strict separation, and partly because the system dpkg database is large and
   therefore slow to read.

 * Nothing should require root, although it may be acceptable to make use of
   root-only facilities if available (but remembering to pay attention to
   performance).
