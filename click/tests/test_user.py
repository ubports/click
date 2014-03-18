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


import json
import os

from gi.repository import Click

from click.json_helpers import json_array_to_python, json_object_to_python
from click.tests.helpers import TestCase, mkfile


class TestClickUser(TestCase):
    def setUp(self):
        super(TestClickUser, self).setUp()
        self.use_temp_dir()
        self.db = Click.DB()
        self.db.add(self.temp_dir)

    def _setUpMultiDB(self):
        self.multi_db = Click.DB()
        self.multi_db.add(os.path.join(self.temp_dir, "custom"))
        self.multi_db.add(os.path.join(self.temp_dir, "click"))
        user_dbs = [
            os.path.join(
                self.multi_db.get(i).props.root, ".click", "users", "user")
            for i in range(self.multi_db.props.size)
        ]
        a_1_0 = os.path.join(self.temp_dir, "custom", "a", "1.0")
        os.makedirs(a_1_0)
        with mkfile(os.path.join(a_1_0, ".click", "info", "a.manifest")) as m:
            json.dump({"name": "a", "version": "1.0"}, m)
        b_2_0 = os.path.join(self.temp_dir, "custom", "b", "2.0")
        os.makedirs(b_2_0)
        with mkfile(os.path.join(b_2_0, ".click", "info", "b.manifest")) as m:
            json.dump({"name": "b", "version": "2.0"}, m)
        a_1_1 = os.path.join(self.temp_dir, "click", "a", "1.1")
        os.makedirs(a_1_1)
        with mkfile(os.path.join(a_1_1, ".click", "info", "a.manifest")) as m:
            json.dump({"name": "a", "version": "1.1"}, m)
        c_0_1 = os.path.join(self.temp_dir, "click", "c", "0.1")
        os.makedirs(c_0_1)
        with mkfile(os.path.join(c_0_1, ".click", "info", "c.manifest")) as m:
            json.dump({"name": "c", "version": "0.1"}, m)
        os.makedirs(user_dbs[0])
        os.symlink(a_1_0, os.path.join(user_dbs[0], "a"))
        os.symlink(b_2_0, os.path.join(user_dbs[0], "b"))
        os.makedirs(user_dbs[1])
        os.symlink(a_1_1, os.path.join(user_dbs[1], "a"))
        os.symlink(c_0_1, os.path.join(user_dbs[1], "c"))
        return user_dbs, Click.User.for_user(self.multi_db, "user")

    def test_new_no_db(self):
        with self.run_in_subprocess(
                "click_get_db_dir", "g_get_user_name") as (enter, preloads):
            enter()
            preloads["click_get_db_dir"].side_effect = (
                lambda: self.make_string(self.temp_dir))
            preloads["g_get_user_name"].side_effect = (
                lambda: self.make_string("test-user"))
            db_root = os.path.join(self.temp_dir, "db")
            os.makedirs(db_root)
            with open(os.path.join(self.temp_dir, "db.conf"), "w") as f:
                print("[Click Database]", file=f)
                print("root = %s" % db_root, file=f)
            registry = Click.User.for_user()
            self.assertEqual(
                os.path.join(db_root, ".click", "users", "test-user"),
                registry.get_overlay_db())

    def test_get_overlay_db(self):
        self.assertEqual(
            os.path.join(self.temp_dir, ".click", "users", "user"),
            Click.User.for_user(self.db, "user").get_overlay_db())

    def test_get_package_names_missing(self):
        db = Click.DB()
        db.add(os.path.join(self.temp_dir, "nonexistent"))
        registry = Click.User.for_user(db)
        self.assertEqual([], list(registry.get_package_names()))

    def test_get_package_names(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(registry.get_overlay_db())
        os.symlink("/1.0", os.path.join(registry.get_overlay_db(), "a"))
        os.symlink("/1.1", os.path.join(registry.get_overlay_db(), "b"))
        self.assertCountEqual(["a", "b"], list(registry.get_package_names()))

    def test_get_package_names_multiple_root(self):
        _, registry = self._setUpMultiDB()
        self.assertCountEqual(
            ["a", "b", "c"], list(registry.get_package_names()))

    def test_get_version_missing(self):
        registry = Click.User.for_user(self.db, "user")
        self.assertRaisesUserError(
            Click.UserError.NO_SUCH_PACKAGE, registry.get_version, "a")
        self.assertFalse(registry.has_package_name("a"))

    def test_get_version(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(registry.get_overlay_db())
        os.symlink("/1.0", os.path.join(registry.get_overlay_db(), "a"))
        self.assertEqual("1.0", registry.get_version("a"))
        self.assertTrue(registry.has_package_name("a"))

    def test_get_version_multiple_root(self):
        _, registry = self._setUpMultiDB()
        self.assertEqual("1.1", registry.get_version("a"))
        self.assertEqual("2.0", registry.get_version("b"))
        self.assertEqual("0.1", registry.get_version("c"))
        self.assertTrue(registry.has_package_name("a"))
        self.assertTrue(registry.has_package_name("b"))
        self.assertTrue(registry.has_package_name("c"))

    def test_set_version_missing_target(self):
        registry = Click.User.for_user(self.db, "user")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST,
            registry.set_version, "a", "1.0")

    def test_set_version_missing(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry.set_version("a", "1.0")
        path = os.path.join(registry.get_overlay_db(), "a")
        self.assertTrue(os.path.islink(path))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "1.0"), os.readlink(path))

    def test_set_version_changed(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(registry.get_overlay_db())
        path = os.path.join(registry.get_overlay_db(), "a")
        os.symlink("/1.0", path)
        os.makedirs(os.path.join(self.temp_dir, "a", "1.1"))
        registry.set_version("a", "1.1")
        self.assertTrue(os.path.islink(path))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "1.1"), os.readlink(path))

    def test_set_version_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()

        os.makedirs(os.path.join(self.multi_db.get(1).props.root, "a", "1.2"))
        registry.set_version("a", "1.2")
        a_underlay = os.path.join(user_dbs[0], "a")
        a_overlay = os.path.join(user_dbs[1], "a")
        self.assertTrue(os.path.islink(a_underlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(0).props.root, "a", "1.0"),
            os.readlink(a_underlay))
        self.assertTrue(os.path.islink(a_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(1).props.root, "a", "1.2"),
            os.readlink(a_overlay))

        os.makedirs(os.path.join(self.multi_db.get(1).props.root, "b", "2.1"))
        registry.set_version("b", "2.1")
        b_underlay = os.path.join(user_dbs[0], "b")
        b_overlay = os.path.join(user_dbs[1], "b")
        self.assertTrue(os.path.islink(b_underlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(0).props.root, "b", "2.0"),
            os.readlink(b_underlay))
        self.assertTrue(os.path.islink(b_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(1).props.root, "b", "2.1"),
            os.readlink(b_overlay))

        os.makedirs(os.path.join(self.multi_db.get(1).props.root, "c", "0.2"))
        registry.set_version("c", "0.2")
        c_underlay = os.path.join(user_dbs[0], "c")
        c_overlay = os.path.join(user_dbs[1], "c")
        self.assertFalse(os.path.islink(c_underlay))
        self.assertTrue(os.path.islink(c_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(1).props.root, "c", "0.2"),
            os.readlink(c_overlay))

        os.makedirs(os.path.join(self.multi_db.get(1).props.root, "d", "3.0"))
        registry.set_version("d", "3.0")
        d_underlay = os.path.join(user_dbs[0], "d")
        d_overlay = os.path.join(user_dbs[1], "d")
        self.assertFalse(os.path.islink(d_underlay))
        self.assertTrue(os.path.islink(d_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(1).props.root, "d", "3.0"),
            os.readlink(d_overlay))

    def test_set_version_restore_to_underlay(self):
        user_dbs, registry = self._setUpMultiDB()
        a_underlay = os.path.join(user_dbs[0], "a")
        a_overlay = os.path.join(user_dbs[1], "a")

        # Initial state: 1.0 in underlay, 1.1 in overlay.
        self.assertTrue(os.path.islink(a_underlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(0).props.root, "a", "1.0"),
            os.readlink(a_underlay))
        self.assertTrue(os.path.islink(a_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(1).props.root, "a", "1.1"),
            os.readlink(a_overlay))

        # Setting to 1.0 (version in underlay) removes overlay link.
        registry.set_version("a", "1.0")
        self.assertTrue(os.path.islink(a_underlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(0).props.root, "a", "1.0"),
            os.readlink(a_underlay))
        self.assertFalse(os.path.islink(a_overlay))

    def test_remove_missing(self):
        registry = Click.User.for_user(self.db, "user")
        self.assertRaisesUserError(
            Click.UserError.NO_SUCH_PACKAGE, registry.remove, "a")

    def test_remove(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(registry.get_overlay_db())
        path = os.path.join(registry.get_overlay_db(), "a")
        os.symlink("/1.0", path)
        registry.remove("a")
        self.assertFalse(os.path.exists(path))

    def test_remove_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        registry.remove("a")
        self.assertFalse(os.path.exists(os.path.join(user_dbs[1], "a")))
        # Exposed underlay.
        self.assertEqual("1.0", registry.get_version("a"))
        registry.remove("b")
        # Hidden.
        self.assertEqual(
            "@hidden", os.readlink(os.path.join(user_dbs[1], "b")))
        self.assertFalse(registry.has_package_name("b"))
        registry.remove("c")
        self.assertFalse(os.path.exists(os.path.join(user_dbs[1], "c")))
        self.assertFalse(registry.has_package_name("c"))
        self.assertRaisesUserError(
            Click.UserError.NO_SUCH_PACKAGE, registry.remove, "d")

    def test_remove_multiple_root_creates_overlay_directory(self):
        multi_db = Click.DB()
        multi_db.add(os.path.join(self.temp_dir, "preinstalled"))
        multi_db.add(os.path.join(self.temp_dir, "click"))
        user_dbs = [
            os.path.join(multi_db.get(i).props.root, ".click", "users", "user")
            for i in range(multi_db.props.size)
        ]
        a_1_0 = os.path.join(self.temp_dir, "preinstalled", "a", "1.0")
        os.makedirs(a_1_0)
        os.makedirs(user_dbs[0])
        os.symlink(a_1_0, os.path.join(user_dbs[0], "a"))
        self.assertFalse(os.path.exists(user_dbs[1]))
        registry = Click.User.for_user(multi_db, "user")
        self.assertEqual("1.0", registry.get_version("a"))
        registry.remove("a")
        self.assertFalse(registry.has_package_name("a"))
        self.assertEqual(
            "@hidden", os.readlink(os.path.join(user_dbs[1], "a")))

    def test_get_path(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry.set_version("a", "1.0")
        self.assertEqual(
            os.path.join(registry.get_overlay_db(), "a"),
            registry.get_path("a"))

    def test_get_path_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        self.assertEqual(
            os.path.join(user_dbs[1], "a"), registry.get_path("a"))
        self.assertEqual(
            os.path.join(user_dbs[0], "b"), registry.get_path("b"))
        self.assertEqual(
            os.path.join(user_dbs[1], "c"), registry.get_path("c"))
        self.assertRaisesUserError(
            Click.UserError.NO_SUCH_PACKAGE, registry.get_path, "d")

    def test_get_manifest(self):
        registry = Click.User.for_user(self.db, "user")
        manifest_path = os.path.join(
            self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
        manifest_obj = {"name": "a", "version": "1.0"}
        with mkfile(manifest_path) as manifest:
            json.dump(manifest_obj, manifest)
        manifest_obj["_directory"] = os.path.join(
            registry.get_overlay_db(), "a")
        manifest_obj["_removable"] = 1
        registry.set_version("a", "1.0")
        self.assertEqual(
            manifest_obj, json_object_to_python(registry.get_manifest("a")))

    def test_get_manifest_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        self.assertEqual({
            "name": "a",
            "version": "1.1",
            "_directory": os.path.join(user_dbs[1], "a"),
            "_removable": 1,
        }, json_object_to_python(registry.get_manifest("a")))
        self.assertEqual({
            "name": "b",
            "version": "2.0",
            "_directory": os.path.join(user_dbs[0], "b"),
            "_removable": 1,
        }, json_object_to_python(registry.get_manifest("b")))
        self.assertEqual({
            "name": "c",
            "version": "0.1",
            "_directory": os.path.join(user_dbs[1], "c"),
            "_removable": 1,
        }, json_object_to_python(registry.get_manifest("c")))
        self.assertRaisesUserError(
            Click.UserError.NO_SUCH_PACKAGE, registry.get_path, "d")

    def test_get_manifests(self):
        registry = Click.User.for_user(self.db, "user")
        a_manifest_path = os.path.join(
            self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
        a_manifest_obj = {"name": "a", "version": "1.0"}
        with mkfile(a_manifest_path) as a_manifest:
            json.dump(a_manifest_obj, a_manifest)
        registry.set_version("a", "1.0")
        b_manifest_path = os.path.join(
            self.temp_dir, "b", "2.0", ".click", "info", "b.manifest")
        b_manifest_obj = {"name": "b", "version": "2.0"}
        with mkfile(b_manifest_path) as b_manifest:
            json.dump(b_manifest_obj, b_manifest)
        registry.set_version("b", "2.0")
        a_manifest_obj["_directory"] = os.path.join(
            registry.get_overlay_db(), "a")
        a_manifest_obj["_removable"] = 1
        b_manifest_obj["_directory"] = os.path.join(
            registry.get_overlay_db(), "b")
        b_manifest_obj["_removable"] = 1
        self.assertEqual(
            [a_manifest_obj, b_manifest_obj],
            json_array_to_python(registry.get_manifests()))

    def test_get_manifests_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        a_manifest_obj = {
            "name": "a",
            "version": "1.1",
            "_directory": os.path.join(user_dbs[1], "a"),
            "_removable": 1,
        }
        b_manifest_obj = {
            "name": "b",
            "version": "2.0",
            "_directory": os.path.join(user_dbs[0], "b"),
            "_removable": 1,
        }
        c_manifest_obj = {
            "name": "c",
            "version": "0.1",
            "_directory": os.path.join(user_dbs[1], "c"),
            "_removable": 1,
        }
        self.assertEqual(
            [a_manifest_obj, c_manifest_obj, b_manifest_obj],
            json_array_to_python(registry.get_manifests()))
        registry.remove("b")
        self.assertEqual(
            "@hidden", os.readlink(os.path.join(user_dbs[1], "b")))
        self.assertEqual(
            [a_manifest_obj, c_manifest_obj],
            json_array_to_python(registry.get_manifests()))

    def test_is_removable(self):
        registry = Click.User.for_user(self.db, "user")
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        registry.set_version("a", "1.0")
        self.assertTrue(registry.is_removable("a"))

    def test_is_removable_multiple_root(self):
        user_dbs, registry = self._setUpMultiDB()
        self.assertTrue(registry.is_removable("a"))
        self.assertTrue(registry.is_removable("b"))
        self.assertTrue(registry.is_removable("c"))
        self.assertFalse(registry.is_removable("d"))

    def test_hidden(self):
        user_dbs, registry = self._setUpMultiDB()
        b_overlay = os.path.join(user_dbs[1], "b")

        registry.remove("b")
        self.assertFalse(registry.has_package_name("b"))
        self.assertTrue(os.path.islink(b_overlay))
        self.assertEqual("@hidden", os.readlink(b_overlay))
        self.assertRaisesUserError(
            Click.UserError.HIDDEN_PACKAGE, registry.get_version, "b")
        self.assertRaisesUserError(
            Click.UserError.HIDDEN_PACKAGE, registry.get_path, "b")
        self.assertFalse(registry.is_removable("b"))

        registry.set_version("b", "2.0")
        self.assertTrue(registry.has_package_name("b"))
        self.assertTrue(os.path.islink(b_overlay))
        self.assertEqual(
            os.path.join(self.multi_db.get(0).props.root, "b", "2.0"),
            os.readlink(b_overlay))
        self.assertEqual("2.0", registry.get_version("b"))
        self.assertEqual(b_overlay, registry.get_path("b"))
        self.assertTrue(registry.is_removable("b"))
