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

from click.database import ClickDB
from click.tests.helpers import TestCase
from click.user import ClickUser


class TestClickUser(TestCase):
    def setUp(self):
        super(TestClickUser, self).setUp()
        self.use_temp_dir()
        self.db = ClickDB(self.temp_dir, use_system=False)

    def _setUpMultiDB(self):
        self.multi_db = ClickDB(use_system=False)
        self.multi_db.add(os.path.join(self.temp_dir, "custom"))
        self.multi_db.add(os.path.join(self.temp_dir, "click"))
        user_dbs = [
            os.path.join(d.root, ".click", "users", "user")
            for d in self.multi_db
        ]
        a_1_0 = os.path.join(self.temp_dir, "custom", "a", "1.0")
        os.makedirs(a_1_0)
        b_2_0 = os.path.join(self.temp_dir, "custom", "b", "2.0")
        os.makedirs(b_2_0)
        a_1_1 = os.path.join(self.temp_dir, "click", "a", "1.1")
        os.makedirs(a_1_1)
        c_0_1 = os.path.join(self.temp_dir, "click", "c", "0.1")
        os.makedirs(c_0_1)
        os.makedirs(user_dbs[0])
        os.symlink(a_1_0, os.path.join(user_dbs[0], "a"))
        os.symlink(b_2_0, os.path.join(user_dbs[0], "b"))
        os.makedirs(user_dbs[1])
        os.symlink(a_1_1, os.path.join(user_dbs[1], "a"))
        os.symlink(c_0_1, os.path.join(user_dbs[1], "c"))
        return user_dbs, ClickUser(self.multi_db, "user")

    def test_overlay_db(self):
        self.assertEqual(
            os.path.join(self.temp_dir, ".click", "users", "user"),
            ClickUser(self.db, "user").overlay_db)

    def test_iter_missing(self):
        db = ClickDB(
            os.path.join(self.temp_dir, "nonexistent"), use_system=False)
        registry = ClickUser(db)
        self.assertEqual([], list(registry))

    def test_iter(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(registry.overlay_db)
        os.symlink("/1.0", os.path.join(registry.overlay_db, "a"))
        os.symlink("/1.1", os.path.join(registry.overlay_db, "b"))
        self.assertCountEqual(["a", "b"], list(registry))

    def test_iter_multiple_root(self):
        _, registry = self._setUpMultiDB()
        self.assertCountEqual(["a", "b", "c"], list(registry))

    def test_len_missing(self):
        db = ClickDB(
            os.path.join(self.temp_dir, "nonexistent"), use_system=False)
        registry = ClickUser(db)
        self.assertEqual(0, len(registry))

    def test_len(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(registry.overlay_db)
        os.symlink("/1.0", os.path.join(registry.overlay_db, "a"))
        os.symlink("/1.1", os.path.join(registry.overlay_db, "b"))
        self.assertEqual(2, len(registry))

    def test_len_multiple_root(self):
        _, registry = self._setUpMultiDB()
        self.assertEqual(3, len(registry))

    def test_getitem_missing(self):
        registry = ClickUser(self.db, "user")
        self.assertRaises(KeyError, registry.__getitem__, "a")

    def test_getitem(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(registry.overlay_db)
        os.symlink("/1.0", os.path.join(registry.overlay_db, "a"))
        self.assertEqual("1.0", registry["a"])

    def test_getitem_multiple_root(self):
        _, registry = self._setUpMultiDB()
        self.assertEqual("1.1", registry["a"])
        self.assertEqual("2.0", registry["b"])
        self.assertEqual("0.1", registry["c"])

    def test_setitem_missing_target(self):
        registry = ClickUser(self.db, "user")
        self.assertRaises(ValueError, registry.__setitem__, "a", "1.0")

    def test_setitem_missing(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry["a"] = "1.0"
        path = os.path.join(registry.overlay_db, "a")
        self.assertTrue(os.path.islink(path))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "1.0"), os.readlink(path))

    def test_setitem_changed(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(registry.overlay_db)
        path = os.path.join(registry.overlay_db, "a")
        os.symlink("/1.0", path)
        os.makedirs(os.path.join(self.temp_dir, "a", "1.1"))
        registry["a"] = "1.1"
        self.assertTrue(os.path.islink(path))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "1.1"), os.readlink(path))

    def test_setitem_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()

        os.makedirs(os.path.join(self.multi_db[1].root, "a", "1.2"))
        registry["a"] = "1.2"
        a_underlay = os.path.join(user_dbs[0], "a")
        a_overlay = os.path.join(user_dbs[1], "a")
        self.assertTrue(os.path.islink(a_underlay))
        self.assertEqual(
            os.path.join(self.multi_db[0].root, "a", "1.0"),
            os.readlink(a_underlay))
        self.assertTrue(os.path.islink(a_overlay))
        self.assertEqual(
            os.path.join(self.multi_db[1].root, "a", "1.2"),
            os.readlink(a_overlay))

        os.makedirs(os.path.join(self.multi_db[1].root, "b", "2.1"))
        registry["b"] = "2.1"
        b_underlay = os.path.join(user_dbs[0], "b")
        b_overlay = os.path.join(user_dbs[1], "b")
        self.assertTrue(os.path.islink(b_underlay))
        self.assertEqual(
            os.path.join(self.multi_db[0].root, "b", "2.0"),
            os.readlink(b_underlay))
        self.assertTrue(os.path.islink(b_overlay))
        self.assertEqual(
            os.path.join(self.multi_db[1].root, "b", "2.1"),
            os.readlink(b_overlay))

        os.makedirs(os.path.join(self.multi_db[1].root, "c", "0.2"))
        registry["c"] = "0.2"
        c_underlay = os.path.join(user_dbs[0], "c")
        c_overlay = os.path.join(user_dbs[1], "c")
        self.assertFalse(os.path.islink(c_underlay))
        self.assertTrue(os.path.islink(c_overlay))
        self.assertEqual(
            os.path.join(self.multi_db[1].root, "c", "0.2"),
            os.readlink(c_overlay))

        os.makedirs(os.path.join(self.multi_db[1].root, "d", "3.0"))
        registry["d"] = "3.0"
        d_underlay = os.path.join(user_dbs[0], "d")
        d_overlay = os.path.join(user_dbs[1], "d")
        self.assertFalse(os.path.islink(d_underlay))
        self.assertTrue(os.path.islink(d_overlay))
        self.assertEqual(
            os.path.join(self.multi_db[1].root, "d", "3.0"),
            os.readlink(d_overlay))

    def test_delitem_missing(self):
        registry = ClickUser(self.db, "user")
        self.assertRaises(KeyError, registry.__delitem__, "a")

    def test_delitem(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(registry.overlay_db)
        path = os.path.join(registry.overlay_db, "a")
        os.symlink("/1.0", path)
        del registry["a"]
        self.assertFalse(os.path.exists(path))

    def test_delitem_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        del registry["a"]
        self.assertFalse(os.path.exists(os.path.join(user_dbs[1], "a")))
        # Strange behaviour; see TODO comment in ClickUser.__delitem__.
        self.assertEqual("1.0", registry["a"])
        self.assertRaises(KeyError, registry.__delitem__, "b")
        del registry["c"]
        self.assertFalse(os.path.exists(os.path.join(user_dbs[1], "c")))
        self.assertNotIn("c", registry)
        self.assertRaises(KeyError, registry.__delitem__, "d")

    def test_path(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry["a"] = "1.0"
        self.assertEqual(
            os.path.join(registry.overlay_db, "a"), registry.path("a"))

    def test_path_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        self.assertEqual(os.path.join(user_dbs[1], "a"), registry.path("a"))
        self.assertEqual(os.path.join(user_dbs[0], "b"), registry.path("b"))
        self.assertEqual(os.path.join(user_dbs[1], "c"), registry.path("c"))
        self.assertRaises(KeyError, registry.path, "d")

    def test_writeable(self):
        registry = ClickUser(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry["a"] = "1.0"
        self.assertTrue(registry.writeable("a"))

    def test_writeable_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        self.assertTrue(registry.writeable("a"))
        self.assertFalse(registry.writeable("b"))
        self.assertTrue(registry.writeable("c"))
        self.assertFalse(registry.writeable("d"))
