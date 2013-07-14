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

"""Unit tests for click.user."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestClickUser',
    ]


import os

from click.tests.helpers import TestCase
from click.user import ClickUser


class TestClickUser(TestCase):
    def setUp(self):
        super(TestClickUser, self).setUp()
        self.use_temp_dir()

    def test_db(self):
        self.assertEqual(
            os.path.join("/click", ".click", "users", "user"),
            ClickUser("/click", "user")._db)

    def test_iter_missing(self):
        registry = ClickUser("/")
        registry._db = os.path.join(self.temp_dir, "nonexistent")
        self.assertEqual([], list(registry))

    def test_iter(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        os.symlink("/1.0", os.path.join(self.temp_dir, "a"))
        os.symlink("/1.1", os.path.join(self.temp_dir, "b"))
        self.assertCountEqual(["a", "b"], list(registry))

    def test_len_missing(self):
        registry = ClickUser("/")
        registry._db = os.path.join(self.temp_dir, "nonexistent")
        self.assertEqual(0, len(registry))

    def test_len(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        os.symlink("/1.0", os.path.join(self.temp_dir, "a"))
        os.symlink("/1.1", os.path.join(self.temp_dir, "b"))
        self.assertEqual(2, len(registry))

    def test_getitem_missing(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        self.assertRaises(KeyError, registry.__getitem__, "a")

    def test_getitem(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        os.symlink("/1.0", os.path.join(self.temp_dir, "a"))
        self.assertEqual("1.0", registry["a"])

    def test_setitem_missing_target(self):
        root = os.path.join(self.temp_dir, "root")
        registry = ClickUser(root)
        registry._db = os.path.join(self.temp_dir, "db")
        self.assertRaises(ValueError, registry.__setitem__, "a", "1.0")

    def test_setitem_missing(self):
        root = os.path.join(self.temp_dir, "root")
        registry = ClickUser(root)
        registry._db = os.path.join(self.temp_dir, "db")
        os.makedirs(os.path.join(root, "a", "1.0"))
        registry["a"] = "1.0"
        path = os.path.join(self.temp_dir, "db", "a")
        self.assertTrue(os.path.islink(path))
        self.assertEqual(os.path.join(root, "a", "1.0"), os.readlink(path))

    def test_setitem_changed(self):
        root = os.path.join(self.temp_dir, "root")
        registry = ClickUser(root)
        registry._db = os.path.join(self.temp_dir, "db")
        os.mkdir(registry._db)
        path = os.path.join(self.temp_dir, "db", "a")
        os.symlink("/1.0", path)
        os.makedirs(os.path.join(root, "a", "1.1"))
        registry["a"] = "1.1"
        self.assertTrue(os.path.islink(path))
        self.assertEqual(os.path.join(root, "a", "1.1"), os.readlink(path))

    def test_delitem_missing(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        self.assertRaises(KeyError, registry.__delitem__, "a")

    def test_delitem(self):
        registry = ClickUser("/")
        registry._db = self.temp_dir
        path = os.path.join(self.temp_dir, "a")
        os.symlink("/1.0", path)
        del registry["a"]
        self.assertFalse(os.path.exists(path))

    def test_path(self):
        root = os.path.join(self.temp_dir, "root")
        registry = ClickUser(root)
        registry._db = os.path.join(self.temp_dir, "db")
        os.makedirs(os.path.join(root, "a", "1.0"))
        registry["a"] = "1.0"
        self.assertEqual(
            os.path.join(self.temp_dir, "db", "a"), registry.path("a"))
