.. Click Packages documentation master file, created by
   sphinx-quickstart on Mon Apr 15 11:34:57 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

==============
Click packages
==============

*Click* is the code name used to describe a packaging format for Ubuntu mobile
applications.  This format specifies how individual apps are delivered to
mobile devices, how they are packed into distributable format, and how they
are installed on a mobile device by a system provided package manager.  At a
minimum they assume that a system framework exists providing all the
necessary infrastructure and dependencies needed in order to install and run
such apps.

The click packaging format is completely independent from facilities to do
full-system installations or upgrades.


Compatibility
=============

Currently, this package should remain compatible with Python 2.7, 3.2, 3.3,
and 3.4; Ubuntu 12.04 LTS, Ubuntu 13.10, and Ubuntu 14.04 LTS.

Build
=====

If you run from a fresh bzr checkout, please ensure you have the required 
build dependencies first by running::

    $ dpkg-checkbuilddeps

and installing anything that is missing here.

Then run::

    $ ./autogen.sh
    $ ./configure --with-systemdsystemunitdir=/lib/systemd/system \
	--with-systemduserunitdir=/usr/lib/systemd/user
    $ make

to build the project.


Dependencies
------------

For Ubuntu 14.04, make sure you have the *python2.7* and *python3.4*
packages installed.  Unless you upgraded from a previous version of Ubuntu
and haven't removed it yet, you won't have Python 3.3 and Python 3.2
available.  Build them from source if necessary, install them say into
``/usr/local``, and make sure they are on your ``$PATH``.

You'll need *tox* (Ubuntu package *python-tox*) installed in order to run the
full test suite.  You should be able to just say::

    $ tox

to run the full suite.  Use tox's ``-e`` option to run the tests against a
subset of Python versions.  You shouldn't have to install anything manually
into the virtual environments that tox creates, but you might have to if you
don't have all the dependencies installed in your system Pythons.

You'll need the *mock* and *python-debian* libraries.  For Ubuntu 13.10,
apt-get install the following packages::

 * python-mock
 * python-debian
 * python3-debian


Testing
=======

After all of the above is installed, you can run ``tox`` to run the test suite
against all supported Python versions.  The ``./run-tests`` scripts just does
an additional check to make sure you've got the preload shared library
built.

To run a specific testcase, use the standard python unittest syntax like::

  $ python3 -m unittest click.tests.test_install

or::

  $ python2 -m unittest click.tests.test_build.TestClickBuilder.test_build



Documentation
=============

To build the HTML version of the documentation, you'll need Sphinx (Ubuntu
package *python-sphinx*).  Then do::

    $ (cd doc && make html)


Contents:

.. toctree::
   :maxdepth: 2

   file-format.rst
   constraints.rst
   hooks.rst
   databases.rst
   todo.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
