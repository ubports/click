# Copyright (C) 2013 Canonical Ltd.
# Author: Colin Watson <cjwatson@ubuntu.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# This file contains code from Python 3.3, released under the Python license
# (http://docs.python.org/3/license.html).

"""Testing helpers."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestCase',
    'mkfile',
    'touch',
    ]


import contextlib
import os
import shutil
import sys
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest
try:
    from unittest import mock
except ImportError:
    import mock

from click import osextras


class TestCase(unittest.TestCase):
    def setUp(self):
        super(TestCase, self).setUp()
        self.temp_dir = None
        self.save_env = dict(os.environ)
        self.maxDiff = None

    def tearDown(self):
        for key in set(os.environ) - set(self.save_env):
            del os.environ[key]
        for key, value in os.environ.items():
            if value != self.save_env[key]:
                os.environ[key] = self.save_env[key]
        for key in set(self.save_env) - set(os.environ):
            os.environ[key] = self.save_env[key]

    def use_temp_dir(self):
        if self.temp_dir is not None:
            return self.temp_dir
        self.temp_dir = tempfile.mkdtemp(prefix="click")
        self.addCleanup(shutil.rmtree, self.temp_dir)
        return self.temp_dir

    # Monkey-patch for Python 2/3 compatibility.
    if not hasattr(unittest.TestCase, 'assertCountEqual'):
        assertCountEqual = unittest.TestCase.assertItemsEqual
    if not hasattr(unittest.TestCase, 'assertRegex'):
        assertRegex = unittest.TestCase.assertRegexpMatches
    # Renamed in Python 3.2 to omit the trailing 'p'.
    if not hasattr(unittest.TestCase, 'assertRaisesRegex'):
        assertRaisesRegex = unittest.TestCase.assertRaisesRegexp


if not hasattr(mock, "call"):
    # mock 0.7.2, the version in Ubuntu 12.04 LTS, lacks mock.ANY and
    # mock.call.  Since it's so convenient, monkey-patch a partial backport
    # (from Python 3.3 unittest.mock) into place here.
    class _ANY(object):
        "A helper object that compares equal to everything."

        def __eq__(self, other):
            return True

        def __ne__(self, other):
            return False

        def __repr__(self):
            return '<ANY>'


    mock.ANY = _ANY()


    class _Call(tuple):
        """
        A tuple for holding the results of a call to a mock, either in the form
        `(args, kwargs)` or `(name, args, kwargs)`.

        If args or kwargs are empty then a call tuple will compare equal to
        a tuple without those values. This makes comparisons less verbose::

            _Call(('name', (), {})) == ('name',)
            _Call(('name', (1,), {})) == ('name', (1,))
            _Call(((), {'a': 'b'})) == ({'a': 'b'},)

        The `_Call` object provides a useful shortcut for comparing with call::

            _Call(((1, 2), {'a': 3})) == call(1, 2, a=3)
            _Call(('foo', (1, 2), {'a': 3})) == call.foo(1, 2, a=3)

        If the _Call has no name then it will match any name.
        """
        def __new__(cls, value=(), name=None, parent=None, two=False,
                    from_kall=True):
            name = ''
            args = ()
            kwargs = {}
            _len = len(value)
            if _len == 3:
                name, args, kwargs = value
            elif _len == 2:
                first, second = value
                if isinstance(first, str):
                    name = first
                    if isinstance(second, tuple):
                        args = second
                    else:
                        kwargs = second
                else:
                    args, kwargs = first, second
            elif _len == 1:
                value, = value
                if isinstance(value, str):
                    name = value
                elif isinstance(value, tuple):
                    args = value
                else:
                    kwargs = value

            if two:
                return tuple.__new__(cls, (args, kwargs))

            return tuple.__new__(cls, (name, args, kwargs))


        def __init__(self, value=(), name=None, parent=None, two=False,
                     from_kall=True):
            self.name = name
            self.parent = parent
            self.from_kall = from_kall


        def __eq__(self, other):
            if other is mock.ANY:
                return True
            try:
                len_other = len(other)
            except TypeError:
                return False

            self_name = ''
            if len(self) == 2:
                self_args, self_kwargs = self
            else:
                self_name, self_args, self_kwargs = self

            other_name = ''
            if len_other == 0:
                other_args, other_kwargs = (), {}
            elif len_other == 3:
                other_name, other_args, other_kwargs = other
            elif len_other == 1:
                value, = other
                if isinstance(value, tuple):
                    other_args = value
                    other_kwargs = {}
                elif isinstance(value, str):
                    other_name = value
                    other_args, other_kwargs = (), {}
                else:
                    other_args = ()
                    other_kwargs = value
            else:
                # len 2
                # could be (name, args) or (name, kwargs) or (args, kwargs)
                first, second = other
                if isinstance(first, str):
                    other_name = first
                    if isinstance(second, tuple):
                        other_args, other_kwargs = second, {}
                    else:
                        other_args, other_kwargs = (), second
                else:
                    other_args, other_kwargs = first, second

            if self_name and other_name != self_name:
                return False

            # this order is important for ANY to work!
            return (other_args, other_kwargs) == (self_args, self_kwargs)


        def __ne__(self, other):
            return not self.__eq__(other)


        def __call__(self, *args, **kwargs):
            if self.name is None:
                return _Call(('', args, kwargs), name='()')

            name = self.name + '()'
            return _Call((self.name, args, kwargs), name=name, parent=self)


        def __getattr__(self, attr):
            if self.name is None:
                return _Call(name=attr, from_kall=False)
            name = '%s.%s' % (self.name, attr)
            return _Call(name=name, parent=self, from_kall=False)


    mock.call = _Call(from_kall=False)


@contextlib.contextmanager
def mkfile(path, mode="w"):
    osextras.ensuredir(os.path.dirname(path))
    with open(path, mode) as f:
        yield f


@contextlib.contextmanager
def mkfile_utf8(path, mode="w"):
    osextras.ensuredir(os.path.dirname(path))
    if sys.version < "3":
        import codecs
        with codecs.open(path, mode, "UTF-8") as f:
            yield f
    else:
        # io.open is available from Python 2.6, but we only use it with
        # Python 3 because it raises exceptions when passed bytes.
        import io
        with io.open(path, mode, encoding="UTF-8") as f:
            yield f


def touch(path):
    with mkfile(path, mode="a"):
        pass
