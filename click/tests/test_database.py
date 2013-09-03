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

"""Unit tests for click.database."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "TestClickDB",
    "TestClickSingleDB",
    ]


import os

from click.database import ClickDB, ClickSingleDB
from click.tests.helpers import TestCase


class TestClickSingleDB(TestCase):
    def setUp(self):
        super(TestClickSingleDB, self).setUp()
        self.use_temp_dir()
        self.db = ClickSingleDB(self.temp_dir)

    def test_path(self):
        path = os.path.join(self.temp_dir, "a", "1.0")
        os.makedirs(path)
        self.assertEqual(path, self.db.path("a", "1.0"))
        self.assertRaises(KeyError, self.db.path, "a", "1.1")

    def test_packages_current(self):
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "a", "1.1"))
        a_current = os.path.join(self.temp_dir, "a", "current")
        os.symlink("1.1", a_current)
        os.makedirs(os.path.join(self.temp_dir, "b", "0.1"))
        b_current = os.path.join(self.temp_dir, "b", "current")
        os.symlink("0.1", b_current)
        os.makedirs(os.path.join(self.temp_dir, "c", "2.0"))
        self.assertEqual([
            ("a", "1.1", a_current),
            ("b", "0.1", b_current),
        ], list(self.db.packages()))

    def test_packages_all(self):
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "a", "1.1"))
        os.symlink("1.1", os.path.join(self.temp_dir, "a", "current"))
        os.makedirs(os.path.join(self.temp_dir, "b", "0.1"))
        os.symlink("0.1", os.path.join(self.temp_dir, "b", "current"))
        os.makedirs(os.path.join(self.temp_dir, "c", "2.0"))
        self.assertEqual([
            ("a", "1.0", os.path.join(self.temp_dir, "a", "1.0")),
            ("a", "1.1", os.path.join(self.temp_dir, "a", "1.1")),
            ("b", "0.1", os.path.join(self.temp_dir, "b", "0.1")),
            ("c", "2.0", os.path.join(self.temp_dir, "c", "2.0")),
        ], list(self.db.packages(all_versions=True)))


class TestClickDB(TestCase):
    def setUp(self):
        super(TestClickDB, self).setUp()
        self.use_temp_dir()

    def test_read_configuration(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = /a", file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = /b", file=b)
        db = ClickDB(extra_root="/c", override_db_dir=self.temp_dir)
        self.assertEqual(3, len(db))
        self.assertEqual(["/a", "/b", "/c"], [d.root for d in db])

    def test_no_use_system(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = /a", file=a)
        db = ClickDB(use_system=False, override_db_dir=self.temp_dir)
        self.assertEqual(0, len(db))

    def test_add(self):
        db = ClickDB(use_system=False)
        self.assertEqual(0, len(db))
        db.add("/new/root")
        self.assertEqual(1, len(db))
        self.assertEqual(["/new/root"], [d.root for d in db])

    def test_overlay(self):
        with open(os.path.join(self.temp_dir, "00_custom.conf"), "w") as f:
            print("[Click Database]", file=f)
            print("root = /custom", file=f)
        with open(os.path.join(self.temp_dir, "99_default.conf"), "w") as f:
            print("[Click Database]", file=f)
            print("root = /opt/click.ubuntu.com", file=f)
        db = ClickDB(override_db_dir=self.temp_dir)
        self.assertEqual("/opt/click.ubuntu.com", db.overlay)

    def test_path(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = ClickDB(override_db_dir=self.temp_dir)
        self.assertRaises(KeyError, db.path, "pkg", "1.0")
        os.makedirs(os.path.join(self.temp_dir, "a", "pkg", "1.0"))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "pkg", "1.0"),
            db.path("pkg", "1.0"))
        self.assertRaises(KeyError, db.path, "pkg", "1.1")
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.0"))
        self.assertEqual(
            os.path.join(self.temp_dir, "b", "pkg", "1.0"),
            db.path("pkg", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.1"))
        self.assertEqual(
            os.path.join(self.temp_dir, "b", "pkg", "1.1"),
            db.path("pkg", "1.1"))

    def test_packages_current(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = ClickDB(override_db_dir=self.temp_dir)
        self.assertEqual([], list(db.packages()))
        os.makedirs(os.path.join(self.temp_dir, "a", "pkg1", "1.0"))
        os.symlink("1.0", os.path.join(self.temp_dir, "a", "pkg1", "current"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg1", "1.1"))
        pkg1_current = os.path.join(self.temp_dir, "b", "pkg1", "current")
        os.symlink("1.1", pkg1_current)
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg2", "0.1"))
        pkg2_current = os.path.join(self.temp_dir, "b", "pkg2", "current")
        os.symlink("0.1", pkg2_current)
        self.assertEqual([
            ("pkg1", "1.1", pkg1_current),
            ("pkg2", "0.1", pkg2_current),
        ], list(db.packages()))

    def test_packages_all(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = ClickDB(override_db_dir=self.temp_dir)
        self.assertEqual([], list(db.packages()))
        os.makedirs(os.path.join(self.temp_dir, "a", "pkg1", "1.0"))
        os.symlink("1.0", os.path.join(self.temp_dir, "a", "pkg1", "current"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg1", "1.1"))
        os.symlink("1.1", os.path.join(self.temp_dir, "b", "pkg1", "current"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg2", "0.1"))
        os.symlink("0.1", os.path.join(self.temp_dir, "b", "pkg2", "current"))
        self.assertEqual([
            ("pkg1", "1.1", os.path.join(self.temp_dir, "b", "pkg1", "1.1")),
            ("pkg2", "0.1", os.path.join(self.temp_dir, "b", "pkg2", "0.1")),
            ("pkg1", "1.0", os.path.join(self.temp_dir, "a", "pkg1", "1.0")),
        ], list(db.packages(all_versions=True)))
