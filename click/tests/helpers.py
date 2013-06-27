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
import tempfile
try:
    import unittest2 as unittest
except ImportError:
    import unittest

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


@contextlib.contextmanager
def mkfile(path, mode="w"):
    osextras.ensuredir(os.path.dirname(path))
    with open(path, mode) as f:
        yield f


def touch(path):
    with mkfile(path, mode="a"):
        pass
