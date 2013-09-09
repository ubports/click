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


import json
import os

from click.database import ClickDB
from click.tests.helpers import TestCase, mkfile, mock


class TestClickSingleDB(TestCase):
    def setUp(self):
        super(TestClickSingleDB, self).setUp()
        self.use_temp_dir()
        self.master_db = ClickDB(extra_root=self.temp_dir, use_system=False)
        self.db = self.master_db._db[-1]

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

    @mock.patch("subprocess.call")
    def test_app_running(self, mock_call):
        mock_call.return_value = 0
        self.assertTrue(self.db._app_running("foo", "bar", "1.0"))
        mock_call.assert_called_once_with(
            ["upstart-app-pid", "foo_bar_1.0"], stdout=mock.ANY)
        mock_call.return_value = 1
        self.assertFalse(self.db._app_running("foo", "bar", "1.0"))

    @mock.patch("click.osextras.find_on_path")
    @mock.patch("subprocess.call")
    def test_any_app_running(self, mock_call, mock_find_on_path):
        manifest_path = os.path.join(
            self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            json.dump({"hooks": {"a-app": {}}}, manifest)
        mock_call.return_value = 0
        mock_find_on_path.return_value = False
        self.assertFalse(self.db._any_app_running("a", "1.0"))
        mock_find_on_path.return_value = True
        self.assertTrue(self.db._any_app_running("a", "1.0"))
        mock_call.assert_called_once_with(
            ["upstart-app-pid", "a_a-app_1.0"], stdout=mock.ANY)
        mock_call.return_value = 1
        self.assertFalse(self.db._any_app_running("a", "1.0"))

    @mock.patch("click.osextras.find_on_path")
    @mock.patch("subprocess.call")
    def test_maybe_remove_registered(self, mock_call, mock_find_on_path):
        version_path = os.path.join(self.temp_dir, "a", "1.0")
        manifest_path = os.path.join(
            version_path, ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            json.dump({"hooks": {"a-app": {}}}, manifest)
        user_path = os.path.join(
            self.temp_dir, ".click", "users", "test-user", "a")
        os.makedirs(os.path.dirname(user_path))
        os.symlink(version_path, user_path)
        mock_call.return_value = 0
        mock_find_on_path.return_value = True
        self.db.maybe_remove("a", "1.0")
        self.assertTrue(os.path.exists(version_path))
        self.assertTrue(os.path.exists(user_path))

    @mock.patch("click.osextras.find_on_path")
    @mock.patch("subprocess.call")
    def test_maybe_remove_running(self, mock_call, mock_find_on_path):
        version_path = os.path.join(self.temp_dir, "a", "1.0")
        manifest_path = os.path.join(
            version_path, ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            json.dump({"hooks": {"a-app": {}}}, manifest)
        mock_call.return_value = 0
        mock_find_on_path.return_value = True
        self.db.maybe_remove("a", "1.0")
        gcinuse_path = os.path.join(
            self.temp_dir, ".click", "users", "@gcinuse", "a")
        self.assertTrue(os.path.islink(gcinuse_path))
        self.assertEqual(version_path, os.readlink(gcinuse_path))
        self.assertTrue(os.path.exists(version_path))
        self.db.maybe_remove("a", "1.0")
        self.assertTrue(os.path.islink(gcinuse_path))
        self.assertEqual(version_path, os.readlink(gcinuse_path))
        self.assertTrue(os.path.exists(version_path))

    @mock.patch("click.osextras.find_on_path")
    @mock.patch("subprocess.call")
    def test_maybe_remove_not_running(self, mock_call, mock_find_on_path):
        version_path = os.path.join(self.temp_dir, "a", "1.0")
        manifest_path = os.path.join(
            version_path, ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            json.dump({"hooks": {"a-app": {}}}, manifest)
        current_path = os.path.join(self.temp_dir, "a", "current")
        os.symlink("1.0", current_path)
        mock_call.return_value = 1
        mock_find_on_path.return_value = True
        self.db.maybe_remove("a", "1.0")
        gcinuse_path = os.path.join(
            self.temp_dir, ".click", "users", "@gcinuse", "a")
        self.assertFalse(os.path.islink(gcinuse_path))
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "a")))

    @mock.patch("click.osextras.find_on_path")
    @mock.patch("subprocess.call")
    def test_gc(self, mock_call, mock_find_on_path):
        a_path = os.path.join(self.temp_dir, "a", "1.0")
        a_manifest_path = os.path.join(a_path, ".click", "info", "a.manifest")
        with mkfile(a_manifest_path) as manifest:
            json.dump({"hooks": {"a-app": {}}}, manifest)
        b_path = os.path.join(self.temp_dir, "b", "1.0")
        b_manifest_path = os.path.join(b_path, ".click", "info", "b.manifest")
        with mkfile(b_manifest_path) as manifest:
            json.dump({"hooks": {"b-app": {}}}, manifest)
        c_path = os.path.join(self.temp_dir, "c", "1.0")
        c_manifest_path = os.path.join(c_path, ".click", "info", "c.manifest")
        with mkfile(c_manifest_path) as manifest:
            json.dump({"hooks": {"c-app": {}}}, manifest)
        a_user_path = os.path.join(
            self.temp_dir, ".click", "users", "test-user", "a")
        os.makedirs(os.path.dirname(a_user_path))
        os.symlink(a_path, a_user_path)
        b_gcinuse_path = os.path.join(
            self.temp_dir, ".click", "users", "@gcinuse", "b")
        os.makedirs(os.path.dirname(b_gcinuse_path))
        os.symlink(b_path, b_gcinuse_path)
        mock_call.return_value = 1
        mock_find_on_path.return_value = True
        self.db.gc(verbose=False)
        self.assertTrue(os.path.exists(a_path))
        self.assertFalse(os.path.exists(b_path))
        self.assertTrue(os.path.exists(c_path))


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
            ("pkg1", "1.1", pkg1_current, True),
            ("pkg2", "0.1", pkg2_current, True),
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
            ("pkg1", "1.1", os.path.join(self.temp_dir, "b", "pkg1", "1.1"),
             True),
            ("pkg2", "0.1", os.path.join(self.temp_dir, "b", "pkg2", "0.1"),
             True),
            ("pkg1", "1.0", os.path.join(self.temp_dir, "a", "pkg1", "1.0"),
             False),
        ], list(db.packages(all_versions=True)))
