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
    "TestClickInstalledPackage",
    "TestClickSingleDB",
    ]


from functools import partial
from itertools import takewhile
import json
import os
import unittest

from gi.repository import Click, GLib

from click.json_helpers import json_array_to_python, json_object_to_python
from click.tests.gimock_types import Passwd
from click.tests.helpers import TestCase, mkfile, touch


class TestClickInstalledPackage(TestCase):
    def setUp(self):
        super(TestClickInstalledPackage, self).setUp()
        self.foo = Click.InstalledPackage.new(
            "foo", "1.0", "/path/to/foo/1.0", False)
        self.foo_clone = Click.InstalledPackage.new(
            "foo", "1.0", "/path/to/foo/1.0", False)
        self.foo_different_version = Click.InstalledPackage.new(
            "foo", "2.0", "/path/to/foo/1.0", False)
        self.foo_different_path = Click.InstalledPackage.new(
            "foo", "1.0", "/path/to/foo/2.0", False)
        self.foo_different_writeable = Click.InstalledPackage.new(
            "foo", "1.0", "/path/to/foo/1.0", True)
        self.bar = Click.InstalledPackage.new(
            "bar", "1.0", "/path/to/foo/1.0", False)

    def test_hash(self):
        self.assertIsInstance(self.foo.hash(), int)
        self.assertEqual(self.foo.hash(), self.foo_clone.hash())
        self.assertNotEqual(self.foo.hash(), self.foo_different_version.hash())
        self.assertNotEqual(self.foo.hash(), self.foo_different_path.hash())
        self.assertNotEqual(
            self.foo.hash(), self.foo_different_writeable.hash())
        self.assertNotEqual(self.foo.hash(), self.bar.hash())

    # GLib doesn't allow passing an InstalledPackage as an argument here.
    @unittest.expectedFailure
    def test_equal_to(self):
        self.assertTrue(self.foo.equal_to(self.foo_clone))
        self.assertFalse(self.foo.equal_to(self.foo_different_version))
        self.assertFalse(self.foo.equal_to(self.foo_different_path))
        self.assertFalse(self.foo.equal_to(self.foo_different_writeable))
        self.assertFalse(self.foo.equal_to(self.bar))


class TestClickSingleDB(TestCase):
    def setUp(self):
        super(TestClickSingleDB, self).setUp()
        self.use_temp_dir()
        self.master_db = Click.DB()
        self.master_db.add(self.temp_dir)
        self.db = self.master_db.get(self.master_db.props.size - 1)
        self.spawn_calls = []

    def g_spawn_sync_side_effect(self, status_map, working_directory, argv,
                                 envp, flags, child_setup, user_data,
                                 standard_output, standard_error, exit_status,
                                 error):
        self.spawn_calls.append(list(takewhile(lambda x: x is not None, argv)))
        if argv[0] in status_map:
            exit_status[0] = status_map[argv[0]]
        else:
            self.delegate_to_original("g_spawn_sync")
        return 0

    def _installed_packages_tuplify(self, ip):
        return [(p.props.package, p.props.version, p.props.path) for p in ip]

    def test_path(self):
        path = os.path.join(self.temp_dir, "a", "1.0")
        os.makedirs(path)
        self.assertEqual(path, self.db.get_path("a", "1.0"))
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST, self.db.get_path, "a", "1.1")

    def test_has_package_version(self):
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        self.assertTrue(self.db.has_package_version("a", "1.0"))
        self.assertFalse(self.db.has_package_version("a", "1.1"))

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
        ], self._installed_packages_tuplify(
            self.db.get_packages(all_versions=False)))

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
        ], self._installed_packages_tuplify(
            self.db.get_packages(all_versions=True)))

    def test_packages_all_ignores_non_directory(self):
        os.makedirs(os.path.join(self.temp_dir, "a", "1.0"))
        touch(os.path.join(self.temp_dir, "file"))
        self.assertEqual([
            ("a", "1.0", os.path.join(self.temp_dir, "a", "1.0")),
        ], self._installed_packages_tuplify(
            self.db.get_packages(all_versions=True)))

    def test_manifest(self):
        manifest_path = os.path.join(
            self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
        manifest_obj = {
            "name": "a", "version": "1.0", "hooks": {"a-app": {}},
            "_should_be_removed": "",
        }
        with mkfile(manifest_path) as manifest:
            json.dump(manifest_obj, manifest)
        del manifest_obj["_should_be_removed"]
        manifest_obj["_directory"] = os.path.join(self.temp_dir, "a", "1.0")
        self.assertEqual(
            manifest_obj,
            json_object_to_python(self.db.get_manifest("a", "1.0")))
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST,
            self.db.get_manifest, "a", "1.1")
        self.assertEqual(
            manifest_obj,
            json.loads(self.db.get_manifest_as_string("a", "1.0")))
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST,
            self.db.get_manifest_as_string, "a", "1.1")

    def test_manifest_bad(self):
        manifest_path = os.path.join(
            self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            print("{bad syntax", file=manifest)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST, self.db.get_manifest, "a", "1.0")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST,
            self.db.get_manifest_as_string, "a", "1.0")
        manifest_path = os.path.join(
            self.temp_dir, "a", "1.1", ".click", "info", "a.manifest")
        with mkfile(manifest_path) as manifest:
            print("[0]", file=manifest)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST, self.db.get_manifest, "a", "1.1")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST,
            self.db.get_manifest_as_string, "a", "1.1")

    def test_app_running(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            preloads["click_find_on_path"].return_value = True
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 0})
            self.assertTrue(self.db.app_running("foo", "bar", "1.0"))
            self.assertEqual(
                [[b"ubuntu-app-pid", b"foo_bar_1.0"]], self.spawn_calls)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 1 << 8})
            self.assertFalse(self.db.app_running("foo", "bar", "1.0"))

    def test_any_app_running_ubuntu_app_pid(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            manifest_path = os.path.join(
                self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            preloads["click_find_on_path"].side_effect = (
                lambda command: command == b"ubuntu-app-pid")
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 0})
            self.assertTrue(self.db.any_app_running("a", "1.0"))
            self.assertEqual(
                [[b"ubuntu-app-pid", b"a_a-app_1.0"]], self.spawn_calls)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 1 << 8})
            self.assertFalse(self.db.any_app_running("a", "1.0"))

    def test_any_app_running_upstart_app_pid(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            manifest_path = os.path.join(
                self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            preloads["click_find_on_path"].side_effect = (
                lambda command: command == b"upstart-app-pid")
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"upstart-app-pid": 0})
            self.assertTrue(self.db.any_app_running("a", "1.0"))
            self.assertEqual(
                [[b"upstart-app-pid", b"a_a-app_1.0"]], self.spawn_calls)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"upstart-app-pid": 1 << 8})
            self.assertFalse(self.db.any_app_running("a", "1.0"))

    def test_any_app_running_no_app_pid_command(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            manifest_path = os.path.join(
                self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            preloads["click_find_on_path"].return_value = False
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 0})
            self.assertFalse(self.db.any_app_running("a", "1.0"))

    def test_any_app_running_missing_app(self):
        with self.run_in_subprocess("click_find_on_path") as (enter, preloads):
            enter()
            preloads["click_find_on_path"].side_effect = (
                lambda command: command == b"ubuntu-app-pid")
            self.assertRaisesDatabaseError(
                Click.DatabaseError.DOES_NOT_EXIST,
                self.db.any_app_running, "a", "1.0")

    def test_any_app_running_bad_manifest(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            manifest_path = os.path.join(
                self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                print("{bad syntax", file=manifest)
            preloads["click_find_on_path"].side_effect = (
                lambda command: command == b"ubuntu-app-pid")
            self.assertFalse(self.db.any_app_running("a", "1.0"))
            self.assertFalse(preloads["g_spawn_sync"].called)

    def test_any_app_running_no_hooks(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            manifest_path = os.path.join(
                self.temp_dir, "a", "1.0", ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({}, manifest)
            preloads["click_find_on_path"].side_effect = (
                lambda command: command == b"ubuntu-app-pid")
            self.assertFalse(self.db.any_app_running("a", "1.0"))
            self.assertFalse(preloads["g_spawn_sync"].called)

    def test_maybe_remove_registered(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            version_path = os.path.join(self.temp_dir, "a", "1.0")
            manifest_path = os.path.join(
                version_path, ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            user_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user", "a")
            os.makedirs(os.path.dirname(user_path))
            os.symlink(version_path, user_path)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 0})
            preloads["click_find_on_path"].return_value = True
            self.db.maybe_remove("a", "1.0")
            self.assertTrue(os.path.exists(version_path))
            self.assertTrue(os.path.exists(user_path))

    def test_maybe_remove_running(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            version_path = os.path.join(self.temp_dir, "a", "1.0")
            manifest_path = os.path.join(
                version_path, ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 0})
            preloads["click_find_on_path"].return_value = True
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

    def test_maybe_remove_not_running(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync",
                ) as (enter, preloads):
            enter()
            os.environ["TEST_QUIET"] = "1"
            version_path = os.path.join(self.temp_dir, "a", "1.0")
            manifest_path = os.path.join(
                version_path, ".click", "info", "a.manifest")
            with mkfile(manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            current_path = os.path.join(self.temp_dir, "a", "current")
            os.symlink("1.0", current_path)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 1 << 8})
            preloads["click_find_on_path"].return_value = True
            self.db.maybe_remove("a", "1.0")
            gcinuse_path = os.path.join(
                self.temp_dir, ".click", "users", "@gcinuse", "a")
            self.assertFalse(os.path.islink(gcinuse_path))
            self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "a")))

    def test_gc(self):
        with self.run_in_subprocess(
                "click_find_on_path", "g_spawn_sync", "getpwnam"
                ) as (enter, preloads):
            enter()
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_uid=1, pw_gid=1)))
            os.environ["TEST_QUIET"] = "1"
            a_path = os.path.join(self.temp_dir, "a", "1.0")
            a_manifest_path = os.path.join(
                a_path, ".click", "info", "a.manifest")
            with mkfile(a_manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            b_path = os.path.join(self.temp_dir, "b", "1.0")
            b_manifest_path = os.path.join(
                b_path, ".click", "info", "b.manifest")
            with mkfile(b_manifest_path) as manifest:
                json.dump({"hooks": {"b-app": {}}}, manifest)
            c_path = os.path.join(self.temp_dir, "c", "1.0")
            c_manifest_path = os.path.join(
                c_path, ".click", "info", "c.manifest")
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
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"ubuntu-app-pid": 1 << 8})
            preloads["click_find_on_path"].return_value = True
            self.db.gc()
            self.assertTrue(os.path.exists(a_path))
            self.assertFalse(os.path.exists(b_path))
            self.assertTrue(os.path.exists(c_path))

    def test_gc_ignores_non_directory(self):
        with self.run_in_subprocess(
                "getpwnam"
                ) as (enter, preloads):
            enter()
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_uid=1, pw_gid=1)))
            a_path = os.path.join(self.temp_dir, "a", "1.0")
            a_manifest_path = os.path.join(
                a_path, ".click", "info", "a.manifest")
            with mkfile(a_manifest_path) as manifest:
                json.dump({"hooks": {"a-app": {}}}, manifest)
            a_user_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user", "a")
            os.makedirs(os.path.dirname(a_user_path))
            os.symlink(a_path, a_user_path)
            touch(os.path.join(self.temp_dir, "file"))
            self.db.gc()
            self.assertTrue(os.path.exists(a_path))

    def _make_ownership_test(self):
        path = os.path.join(self.temp_dir, "a", "1.0")
        touch(os.path.join(path, ".click", "info", "a.manifest"))
        os.symlink("1.0", os.path.join(self.temp_dir, "a", "current"))
        user_path = os.path.join(
            self.temp_dir, ".click", "users", "test-user", "a")
        os.makedirs(os.path.dirname(user_path))
        os.symlink(path, user_path)
        touch(os.path.join(self.temp_dir, ".click", "log"))

    def _set_stat_side_effect(self, preloads, side_effect, limit):
        limit = limit.encode()
        preloads["__xstat"].side_effect = (
            lambda ver, path, buf: side_effect(
                "__xstat", limit, ver, path, buf))
        preloads["__xstat64"].side_effect = (
            lambda ver, path, buf: side_effect(
                "__xstat64", limit, ver, path, buf))

    def test_ensure_ownership_quick_if_correct(self):
        def stat_side_effect(name, limit, ver, path, buf):
            st = self.convert_stat_pointer(name, buf)
            if path == limit:
                st.st_uid = 1
                st.st_gid = 1
                return 0
            else:
                self.delegate_to_original(name)
                return -1

        with self.run_in_subprocess(
                "chown", "getpwnam", "__xstat", "__xstat64",
                ) as (enter, preloads):
            enter()
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_uid=1, pw_gid=1)))
            self._set_stat_side_effect(
                preloads, stat_side_effect, self.db.props.root)

            self._make_ownership_test()
            self.db.ensure_ownership()
            self.assertFalse(preloads["chown"].called)

    def test_ensure_ownership(self):
        def stat_side_effect(name, limit, ver, path, buf):
            st = self.convert_stat_pointer(name, buf)
            if path == limit:
                st.st_uid = 2
                st.st_gid = 2
                return 0
            else:
                self.delegate_to_original(name)
                return -1

        with self.run_in_subprocess(
                "chown", "getpwnam", "__xstat", "__xstat64",
                ) as (enter, preloads):
            enter()
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_uid=1, pw_gid=1)))
            self._set_stat_side_effect(
                preloads, stat_side_effect, self.db.props.root)

            self._make_ownership_test()
            self.db.ensure_ownership()
            expected_paths = [
                self.temp_dir,
                os.path.join(self.temp_dir, ".click"),
                os.path.join(self.temp_dir, ".click", "log"),
                os.path.join(self.temp_dir, ".click", "users"),
                os.path.join(self.temp_dir, "a"),
                os.path.join(self.temp_dir, "a", "1.0"),
                os.path.join(self.temp_dir, "a", "1.0", ".click"),
                os.path.join(self.temp_dir, "a", "1.0", ".click", "info"),
                os.path.join(
                    self.temp_dir, "a", "1.0", ".click", "info", "a.manifest"),
                os.path.join(self.temp_dir, "a", "current"),
                ]
            self.assertCountEqual(
                [path.encode() for path in expected_paths],
                [args[0][0] for args in preloads["chown"].call_args_list])
            self.assertCountEqual(
                [(1, 1)],
                set(args[0][1:] for args in preloads["chown"].call_args_list))

    def test_ensure_ownership_missing_clickpkg_user(self):
        with self.run_in_subprocess("getpwnam") as (enter, preloads):
            enter()
            preloads["getpwnam"].return_value = None
            self.assertRaisesDatabaseError(
                Click.DatabaseError.ENSURE_OWNERSHIP, self.db.ensure_ownership)

    def test_ensure_ownership_failed_chown(self):
        def stat_side_effect(name, limit, ver, path, buf):
            st = self.convert_stat_pointer(name, buf)
            if path == limit:
                st.st_uid = 2
                st.st_gid = 2
                return 0
            else:
                self.delegate_to_original(name)
                return -1

        with self.run_in_subprocess(
                "chown", "getpwnam", "__xstat", "__xstat64",
                ) as (enter, preloads):
            enter()
            preloads["chown"].return_value = -1
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_uid=1, pw_gid=1)))
            self._set_stat_side_effect(
                preloads, stat_side_effect, self.db.props.root)

            self._make_ownership_test()
            self.assertRaisesDatabaseError(
                Click.DatabaseError.ENSURE_OWNERSHIP, self.db.ensure_ownership)


class TestClickDB(TestCase):
    def setUp(self):
        super(TestClickDB, self).setUp()
        self.use_temp_dir()

    def _installed_packages_tuplify(self, ip):
        return [
            (p.props.package, p.props.version, p.props.path, p.props.writeable)
            for p in ip]

    def test_read_configuration(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = /a", file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = /b", file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        db.add("/c")
        self.assertEqual(3, db.props.size)
        self.assertEqual(
            ["/a", "/b", "/c"],
            [db.get(i).props.root for i in range(db.props.size)])

    def test_no_read(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = /a", file=a)
        db = Click.DB()
        self.assertEqual(0, db.props.size)

    def test_read_nonexistent(self):
        db = Click.DB()
        db.read(db_dir=os.path.join(self.temp_dir, "nonexistent"))
        self.assertEqual(0, db.props.size)

    def test_read_not_directory(self):
        path = os.path.join(self.temp_dir, "file")
        touch(path)
        db = Click.DB()
        self.assertRaisesFileError(GLib.FileError.NOTDIR, db.read, db_dir=path)

    def test_add(self):
        db = Click.DB()
        self.assertEqual(0, db.props.size)
        db.add("/new/root")
        self.assertEqual(1, db.props.size)
        self.assertEqual("/new/root", db.get(0).props.root)

    def test_overlay(self):
        with open(os.path.join(self.temp_dir, "00_custom.conf"), "w") as f:
            print("[Click Database]", file=f)
            print("root = /custom", file=f)
        with open(os.path.join(self.temp_dir, "99_default.conf"), "w") as f:
            print("[Click Database]", file=f)
            print("root = /opt/click.ubuntu.com", file=f)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertEqual("/opt/click.ubuntu.com", db.props.overlay)

    def test_path(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST, db.get_path, "pkg", "1.0")
        os.makedirs(os.path.join(self.temp_dir, "a", "pkg", "1.0"))
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "pkg", "1.0"),
            db.get_path("pkg", "1.0"))
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST, db.get_path, "pkg", "1.1")
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.0"))
        # The deepest copy of the same package/version is still preferred.
        self.assertEqual(
            os.path.join(self.temp_dir, "a", "pkg", "1.0"),
            db.get_path("pkg", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.1"))
        self.assertEqual(
            os.path.join(self.temp_dir, "b", "pkg", "1.1"),
            db.get_path("pkg", "1.1"))

    def test_has_package_version(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertFalse(db.has_package_version("pkg", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "a", "pkg", "1.0"))
        self.assertTrue(db.has_package_version("pkg", "1.0"))
        self.assertFalse(db.has_package_version("pkg", "1.1"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.0"))
        self.assertTrue(db.has_package_version("pkg", "1.0"))
        os.makedirs(os.path.join(self.temp_dir, "b", "pkg", "1.1"))
        self.assertTrue(db.has_package_version("pkg", "1.1"))

    def test_packages_current(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertEqual([], list(db.get_packages(all_versions=False)))
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
        ], self._installed_packages_tuplify(
            db.get_packages(all_versions=False)))

    def test_packages_all(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertEqual([], list(db.get_packages(all_versions=True)))
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
        ], self._installed_packages_tuplify(
            db.get_packages(all_versions=True)))

    def test_manifest(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST, db.get_manifest, "pkg", "1.0")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST,
            db.get_manifest_as_string, "pkg", "1.0")
        a_manifest_path = os.path.join(
            self.temp_dir, "a", "pkg", "1.0", ".click", "info", "pkg.manifest")
        a_manifest_obj = {"name": "pkg", "version": "1.0"}
        with mkfile(a_manifest_path) as a_manifest:
            json.dump(a_manifest_obj, a_manifest)
        a_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "a", "pkg", "1.0")
        self.assertEqual(
            a_manifest_obj,
            json_object_to_python(db.get_manifest("pkg", "1.0")))
        self.assertEqual(
            a_manifest_obj,
            json.loads(db.get_manifest_as_string("pkg", "1.0")))
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST, db.get_manifest, "pkg", "1.1")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.DOES_NOT_EXIST,
            db.get_manifest_as_string, "pkg", "1.1")
        b_manifest_path = os.path.join(
            self.temp_dir, "b", "pkg", "1.1", ".click", "info", "pkg.manifest")
        b_manifest_obj = {"name": "pkg", "version": "1.1"}
        with mkfile(b_manifest_path) as b_manifest:
            json.dump(b_manifest_obj, b_manifest)
        b_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "b", "pkg", "1.1")
        self.assertEqual(
            b_manifest_obj,
            json_object_to_python(db.get_manifest("pkg", "1.1")))
        self.assertEqual(
            b_manifest_obj,
            json.loads(db.get_manifest_as_string("pkg", "1.1")))

    def test_manifest_bad(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        manifest_path = os.path.join(
            self.temp_dir, "a", "pkg", "1.0", ".click", "info", "pkg.manifest")
        with mkfile(manifest_path) as manifest:
            print("{bad syntax", file=manifest)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST, db.get_manifest, "pkg", "1.0")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST,
            db.get_manifest_as_string, "pkg", "1.0")
        manifest_path = os.path.join(
            self.temp_dir, "a", "pkg", "1.1", ".click", "info", "pkg.manifest")
        with mkfile(manifest_path) as manifest:
            print("[0]", file=manifest)
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST, db.get_manifest, "pkg", "1.0")
        self.assertRaisesDatabaseError(
            Click.DatabaseError.BAD_MANIFEST,
            db.get_manifest_as_string, "pkg", "1.0")

    def test_manifests_current(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertEqual(
            [], json_array_to_python(db.get_manifests(all_versions=False)))
        self.assertEqual(
            [], json.loads(db.get_manifests_as_string(all_versions=False)))
        a_pkg1_manifest_path = os.path.join(
            self.temp_dir, "a", "pkg1", "1.0",
            ".click", "info", "pkg1.manifest")
        a_pkg1_manifest_obj = {"name": "pkg1", "version": "1.0"}
        with mkfile(a_pkg1_manifest_path) as a_pkg1_manifest:
            json.dump(a_pkg1_manifest_obj, a_pkg1_manifest)
        os.symlink("1.0", os.path.join(self.temp_dir, "a", "pkg1", "current"))
        b_pkg1_manifest_path = os.path.join(
            self.temp_dir, "b", "pkg1", "1.1",
            ".click", "info", "pkg1.manifest")
        b_pkg1_manifest_obj = {"name": "pkg1", "version": "1.1"}
        with mkfile(b_pkg1_manifest_path) as b_pkg1_manifest:
            json.dump(b_pkg1_manifest_obj, b_pkg1_manifest)
        os.symlink("1.1", os.path.join(self.temp_dir, "b", "pkg1", "current"))
        b_pkg2_manifest_path = os.path.join(
            self.temp_dir, "b", "pkg2", "0.1",
            ".click", "info", "pkg2.manifest")
        b_pkg2_manifest_obj = {"name": "pkg2", "version": "0.1"}
        with mkfile(b_pkg2_manifest_path) as b_pkg2_manifest:
            json.dump(b_pkg2_manifest_obj, b_pkg2_manifest)
        os.symlink("0.1", os.path.join(self.temp_dir, "b", "pkg2", "current"))
        b_pkg1_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "b", "pkg1", "1.1")
        b_pkg1_manifest_obj["_removable"] = 1
        b_pkg2_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "b", "pkg2", "0.1")
        b_pkg2_manifest_obj["_removable"] = 1
        self.assertEqual(
            [b_pkg1_manifest_obj, b_pkg2_manifest_obj],
            json_array_to_python(db.get_manifests(all_versions=False)))
        self.assertEqual(
            [b_pkg1_manifest_obj, b_pkg2_manifest_obj],
            json.loads(db.get_manifests_as_string(all_versions=False)))

    def test_manifests_all(self):
        with open(os.path.join(self.temp_dir, "a.conf"), "w") as a:
            print("[Click Database]", file=a)
            print("root = %s" % os.path.join(self.temp_dir, "a"), file=a)
        with open(os.path.join(self.temp_dir, "b.conf"), "w") as b:
            print("[Click Database]", file=b)
            print("root = %s" % os.path.join(self.temp_dir, "b"), file=b)
        db = Click.DB()
        db.read(db_dir=self.temp_dir)
        self.assertEqual(
            [], json_array_to_python(db.get_manifests(all_versions=True)))
        self.assertEqual(
            [], json.loads(db.get_manifests_as_string(all_versions=True)))
        a_pkg1_manifest_path = os.path.join(
            self.temp_dir, "a", "pkg1", "1.0",
            ".click", "info", "pkg1.manifest")
        a_pkg1_manifest_obj = {"name": "pkg1", "version": "1.0"}
        with mkfile(a_pkg1_manifest_path) as a_pkg1_manifest:
            json.dump(a_pkg1_manifest_obj, a_pkg1_manifest)
        os.symlink("1.0", os.path.join(self.temp_dir, "a", "pkg1", "current"))
        b_pkg1_manifest_path = os.path.join(
            self.temp_dir, "b", "pkg1", "1.1",
            ".click", "info", "pkg1.manifest")
        b_pkg1_manifest_obj = {"name": "pkg1", "version": "1.1"}
        with mkfile(b_pkg1_manifest_path) as b_pkg1_manifest:
            json.dump(b_pkg1_manifest_obj, b_pkg1_manifest)
        os.symlink("1.1", os.path.join(self.temp_dir, "b", "pkg1", "current"))
        b_pkg2_manifest_path = os.path.join(
            self.temp_dir, "b", "pkg2", "0.1",
            ".click", "info", "pkg2.manifest")
        b_pkg2_manifest_obj = {"name": "pkg2", "version": "0.1"}
        with mkfile(b_pkg2_manifest_path) as b_pkg2_manifest:
            json.dump(b_pkg2_manifest_obj, b_pkg2_manifest)
        os.symlink("0.1", os.path.join(self.temp_dir, "b", "pkg2", "current"))
        a_pkg1_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "a", "pkg1", "1.0")
        a_pkg1_manifest_obj["_removable"] = 0
        b_pkg1_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "b", "pkg1", "1.1")
        b_pkg1_manifest_obj["_removable"] = 1
        b_pkg2_manifest_obj["_directory"] = os.path.join(
            self.temp_dir, "b", "pkg2", "0.1")
        b_pkg2_manifest_obj["_removable"] = 1
        self.assertEqual(
            [b_pkg1_manifest_obj, b_pkg2_manifest_obj, a_pkg1_manifest_obj],
            json_array_to_python(db.get_manifests(all_versions=True)))
        self.assertEqual(
            [b_pkg1_manifest_obj, b_pkg2_manifest_obj, a_pkg1_manifest_obj],
            json.loads(db.get_manifests_as_string(all_versions=True)))
