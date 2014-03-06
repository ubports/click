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

"""Unit tests for click.hooks."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "TestClickHookSystemLevel",
    "TestClickHookUserLevel",
    "TestClickPatternFormatter",
    "TestPackageInstallHooks",
    "TestPackageRemoveHooks",
    ]


from functools import partial
from itertools import takewhile
import json
import os
from textwrap import dedent

from gi.repository import Click, GLib

from click.tests.gimock_types import Passwd
from click.tests.helpers import TestCase, mkfile, mkfile_utf8


class TestClickPatternFormatter(TestCase):
    def _make_variant(self, **kwargs):
        # pygobject's Variant creator can't handle maybe types, so we have
        # to do this by hand.
        builder = GLib.VariantBuilder.new(GLib.VariantType.new("a{sms}"))
        for key, value in kwargs.items():
            entry = GLib.VariantBuilder.new(GLib.VariantType.new("{sms}"))
            entry.add_value(GLib.Variant.new_string(key))
            entry.add_value(GLib.Variant.new_maybe(
                GLib.VariantType.new("s"),
                None if value is None else GLib.Variant.new_string(value)))
            builder.add_value(entry.end())
        return builder.end()

    def test_expands_provided_keys(self):
        self.assertEqual(
            "foo.bar",
            Click.pattern_format("foo.${key}", self._make_variant(key="bar")))
        self.assertEqual(
            "foo.barbaz",
            Click.pattern_format(
                "foo.${key1}${key2}",
                self._make_variant(key1="bar", key2="baz")))

    def test_expands_missing_keys_to_empty_string(self):
        self.assertEqual(
            "xy", Click.pattern_format("x${key}y", self._make_variant()))

    def test_preserves_unmatched_dollar(self):
        self.assertEqual("$", Click.pattern_format("$", self._make_variant()))
        self.assertEqual(
            "$ {foo}", Click.pattern_format("$ {foo}", self._make_variant()))
        self.assertEqual(
            "x${y",
            Click.pattern_format("${key}${y", self._make_variant(key="x")))

    def test_double_dollar(self):
        self.assertEqual("$", Click.pattern_format("$$", self._make_variant()))
        self.assertEqual(
            "${foo}", Click.pattern_format("$${foo}", self._make_variant()))
        self.assertEqual(
            "x$y",
            Click.pattern_format("x$$${key}", self._make_variant(key="y")))

    def test_possible_expansion(self):
        self.assertEqual(
            {"id": "abc"},
            Click.pattern_possible_expansion(
                "x_abc_1", "x_${id}_${num}",
                self._make_variant(num="1")).unpack())
        self.assertIsNone(
            Click.pattern_possible_expansion(
                "x_abc_1", "x_${id}_${num}", self._make_variant(num="2")))


class TestClickHookBase(TestCase):
    def setUp(self):
        super(TestClickHookBase, self).setUp()
        self.use_temp_dir()
        self.db = Click.DB()
        self.db.add(self.temp_dir)
        self.spawn_calls = []

    def _setup_hooks_dir(self, preloads, hooks_dir=None):
        if hooks_dir is None:
            hooks_dir = self.temp_dir
        preloads["click_get_hooks_dir"].side_effect = (
            lambda: self.make_string(hooks_dir))

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


class TestClickHookSystemLevel(TestClickHookBase):
    def test_open(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print(dedent("""\
                    Pattern: /usr/share/test/${id}.test
                    # Comment
                    Exec: test-update
                    User: root
                    """), file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertCountEqual(
                ["pattern", "exec", "user"], hook.get_fields())
            self.assertEqual(
                "/usr/share/test/${id}.test", hook.get_field("pattern"))
            self.assertEqual("test-update", hook.get_field("exec"))
            self.assertFalse(hook.props.is_user_level)

    def test_hook_name_absent(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: /usr/share/test/${id}.test", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual("test", hook.get_hook_name())

    def test_hook_name_present(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: /usr/share/test/${id}.test", file=f)
                print("Hook-Name: other", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual("other", hook.get_hook_name())

    def test_invalid_app_id(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print(dedent("""\
                    Pattern: /usr/share/test/${id}.test
                    # Comment
                    Exec: test-update
                    User: root
                    """), file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertRaisesHooksError(
                Click.HooksError.BAD_APP_NAME, hook.get_app_id,
                "package", "0.1", "app_name")
            self.assertRaisesHooksError(
                Click.HooksError.BAD_APP_NAME, hook.get_app_id,
                "package", "0.1", "app/name")

    def test_short_id_invalid(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: /usr/share/test/${short-id}.test", file=f)
            hook = Click.Hook.open(self.db, "test")
            # It would perhaps be better if unrecognised $-expansions raised
            # KeyError, but they don't right now.
            self.assertEqual(
                "/usr/share/test/.test",
                hook.get_pattern("package", "0.1", "app-name"))

    def test_short_id_valid_with_single_version(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: /usr/share/test/${short-id}.test", file=f)
                print("Single-Version: yes", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual(
                "/usr/share/test/package_app-name.test",
                hook.get_pattern("package", "0.1", "app-name"))

    def test_run_commands(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "g_spawn_sync") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"/bin/sh": 0})
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Exec: test-update", file=f)
                print("User: root", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual(
                "root", hook.get_run_commands_user(user_name=None))
            hook.run_commands(user_name=None)
            self.assertEqual(
                [[b"/bin/sh", b"-c", b"test-update"]], self.spawn_calls)

    def test_install_package(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            os.makedirs(
                os.path.join(self.temp_dir, "org.example.package", "1.0"))
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo/bar")
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            target_path = os.path.join(
                self.temp_dir, "org.example.package", "1.0", "foo", "bar")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_install_package_trailing_slash(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: %s/${id}/" % self.temp_dir, file=f)
            os.makedirs(
                os.path.join(self.temp_dir, "org.example.package", "1.0"))
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo")
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0")
            target_path = os.path.join(
                self.temp_dir, "org.example.package", "1.0", "foo")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_upgrade(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            os.symlink("old-target", symlink_path)
            os.makedirs(
                os.path.join(self.temp_dir, "org.example.package", "1.0"))
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo/bar")
            target_path = os.path.join(
                self.temp_dir, "org.example.package", "1.0", "foo", "bar")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_remove_package(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            os.symlink("old-target", symlink_path)
            hook = Click.Hook.open(self.db, "test")
            hook.remove_package("org.example.package", "1.0", "test-app")
            self.assertFalse(os.path.exists(symlink_path))

    def test_install(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            with mkfile(os.path.join(self.temp_dir, "hooks", "new.hook")) as f:
                print("Pattern: %s/${id}.new" % self.temp_dir, file=f)
            with mkfile_utf8(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({
                    "maintainer":
                        b"Unic\xc3\xb3de <unicode@example.org>".decode(
                            "UTF-8"),
                    "hooks": {"test1-app": {"new": "target-1"}},
                }, f, ensure_ascii=False)
            os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
            with mkfile_utf8(os.path.join(
                    self.temp_dir, "test-2", "2.0", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({
                    "maintainer":
                        b"Unic\xc3\xb3de <unicode@example.org>".decode(
                            "UTF-8"),
                    "hooks": {"test1-app": {"new": "target-2"}},
                }, f, ensure_ascii=False)
            os.symlink("2.0", os.path.join(self.temp_dir, "test-2", "current"))
            hook = Click.Hook.open(self.db, "new")
            hook.install()
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.new")
            self.assertTrue(os.path.lexists(path_1))
            self.assertEqual(
                os.path.join(self.temp_dir, "test-1", "1.0", "target-1"),
                os.readlink(path_1))
            path_2 = os.path.join(self.temp_dir, "test-2_test1-app_2.0.new")
            self.assertTrue(os.path.lexists(path_2))
            self.assertEqual(
                os.path.join(self.temp_dir, "test-2", "2.0", "target-2"),
                os.readlink(path_2))

    def test_remove(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            with mkfile(os.path.join(self.temp_dir, "hooks", "old.hook")) as f:
                print("Pattern: %s/${id}.old" % self.temp_dir, file=f)
            with mkfile(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({"hooks": {"test1-app": {"old": "target-1"}}}, f)
            os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.old")
            os.symlink(
                os.path.join(self.temp_dir, "test-1", "1.0", "target-1"),
                path_1)
            with mkfile(os.path.join(
                    self.temp_dir, "test-2", "2.0", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({"hooks": {"test2-app": {"old": "target-2"}}}, f)
            os.symlink("2.0", os.path.join(self.temp_dir, "test-2", "current"))
            path_2 = os.path.join(self.temp_dir, "test-2_test2-app_2.0.old")
            os.symlink(
                os.path.join(self.temp_dir, "test-2", "2.0", "target-2"),
                path_2)
            hook = Click.Hook.open(self.db, "old")
            hook.remove()
            self.assertFalse(os.path.exists(path_1))
            self.assertFalse(os.path.exists(path_2))

    def test_sync(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            with mkfile(os.path.join(
                    self.temp_dir, "hooks", "test.hook")) as f:
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            with mkfile(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({"hooks": {"test1-app": {"test": "target-1"}}}, f)
            os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
            with mkfile(os.path.join(
                    self.temp_dir, "test-2", "1.1", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({"hooks": {"test2-app": {"test": "target-2"}}}, f)
            os.symlink("1.1", os.path.join(self.temp_dir, "test-2", "current"))
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.test")
            os.symlink(
                os.path.join(self.temp_dir, "test-1", "1.0", "target-1"),
                path_1)
            path_2 = os.path.join(self.temp_dir, "test-2_test2-app_1.1.test")
            path_3 = os.path.join(self.temp_dir, "test-3_test3-app_1.0.test")
            os.symlink(
                os.path.join(self.temp_dir, "test-3", "1.0", "target-3"),
                path_3)
            hook = Click.Hook.open(self.db, "test")
            hook.sync()
            self.assertTrue(os.path.lexists(path_1))
            self.assertEqual(
                os.path.join(self.temp_dir, "test-1", "1.0", "target-1"),
                os.readlink(path_1))
            self.assertTrue(os.path.lexists(path_2))
            self.assertEqual(
                os.path.join(self.temp_dir, "test-2", "1.1", "target-2"),
                os.readlink(path_2))
            self.assertFalse(os.path.lexists(path_3))


class TestClickHookUserLevel(TestClickHookBase):
    def test_open(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print(dedent("""\
                    User-Level: yes
                    Pattern: ${home}/.local/share/test/${id}.test
                    # Comment
                    Exec: test-update
                    """), file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertCountEqual(
                ["user-level", "pattern", "exec"], hook.get_fields())
            self.assertEqual(
                "${home}/.local/share/test/${id}.test",
                hook.get_field("pattern"))
            self.assertEqual("test-update", hook.get_field("exec"))
            self.assertTrue(hook.props.is_user_level)

    def test_hook_name_absent(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: ${home}/.local/share/test/${id}.test", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual("test", hook.get_hook_name())

    def test_hook_name_present(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: ${home}/.local/share/test/${id}.test", file=f)
                print("Hook-Name: other", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual("other", hook.get_hook_name())

    def test_invalid_app_id(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print(dedent("""\
                    User-Level: yes
                    Pattern: ${home}/.local/share/test/${id}.test
                    # Comment
                    Exec: test-update
                    """), file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertRaisesHooksError(
                Click.HooksError.BAD_APP_NAME, hook.get_app_id,
                "package", "0.1", "app_name")
            self.assertRaisesHooksError(
                Click.HooksError.BAD_APP_NAME, hook.get_app_id,
                "package", "0.1", "app/name")

    def test_short_id_valid(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "getpwnam") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["getpwnam"].side_effect = (
                lambda name: self.make_pointer(Passwd(pw_dir=b"/mock")))
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print(
                    "Pattern: ${home}/.local/share/test/${short-id}.test",
                    file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual(
                "/mock/.local/share/test/package_app-name.test",
                hook.get_pattern(
                    "package", "0.1", "app-name", user_name="mock"))

    def test_run_commands(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "g_spawn_sync") as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["g_spawn_sync"].side_effect = partial(
                self.g_spawn_sync_side_effect, {b"/bin/sh": 0})
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Exec: test-update", file=f)
            hook = Click.Hook.open(self.db, "test")
            self.assertEqual(
                "test-user", hook.get_run_commands_user(user_name="test-user"))
            hook.run_commands(user_name="test-user")
            self.assertEqual(
                [[b"/bin/sh", b"-c", b"test-update"]], self.spawn_calls)

    def test_install_package(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            os.makedirs(os.path.join(
                self.temp_dir, "org.example.package", "1.0"))
            user_db = Click.User.for_user(self.db, "test-user")
            user_db.set_version("org.example.package", "1.0")
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo/bar",
                user_name="test-user")
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            target_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user",
                "org.example.package", "foo", "bar")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_install_package_trailing_slash(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            os.makedirs(os.path.join(
                self.temp_dir, "org.example.package", "1.0"))
            user_db = Click.User.for_user(self.db, "test-user")
            user_db.set_version("org.example.package", "1.0")
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}/" % self.temp_dir, file=f)
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo",
                user_name="test-user")
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0")
            target_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user",
                "org.example.package", "foo")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_install_package_removes_previous(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            os.makedirs(os.path.join(
                self.temp_dir, "org.example.package", "1.0"))
            os.makedirs(os.path.join(
                self.temp_dir, "org.example.package", "1.1"))
            user_db = Click.User.for_user(self.db, "test-user")
            user_db.set_version("org.example.package", "1.0")
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo/bar",
                user_name="test-user")
            hook.install_package(
                "org.example.package", "1.1", "test-app", "foo/bar",
                user_name="test-user")
            old_symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.1.test")
            self.assertFalse(os.path.islink(old_symlink_path))
            self.assertTrue(os.path.islink(symlink_path))
            target_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user",
                "org.example.package", "foo", "bar")
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_upgrade(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            os.symlink("old-target", symlink_path)
            os.makedirs(os.path.join(
                self.temp_dir, "org.example.package", "1.0"))
            user_db = Click.User.for_user(self.db, "test-user")
            user_db.set_version("org.example.package", "1.0")
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            hook = Click.Hook.open(self.db, "test")
            hook.install_package(
                "org.example.package", "1.0", "test-app", "foo/bar",
                user_name="test-user")
            target_path = os.path.join(
                self.temp_dir, ".click", "users", "test-user",
                "org.example.package", "foo", "bar")
            self.assertTrue(os.path.islink(symlink_path))
            self.assertEqual(target_path, os.readlink(symlink_path))

    def test_remove_package(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            symlink_path = os.path.join(
                self.temp_dir, "org.example.package_test-app_1.0.test")
            os.symlink("old-target", symlink_path)
            hook = Click.Hook.open(self.db, "test")
            hook.remove_package(
                "org.example.package", "1.0", "test-app",
                user_name="test-user")
            self.assertFalse(os.path.exists(symlink_path))

    def test_install(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            with mkfile(os.path.join(self.temp_dir, "hooks", "new.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.new" % self.temp_dir, file=f)
            user_db = Click.User.for_user(self.db, "test-user")
            with mkfile_utf8(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({
                    "maintainer":
                        b"Unic\xc3\xb3de <unicode@example.org>".decode(
                            "UTF-8"),
                    "hooks": {"test1-app": {"new": "target-1"}},
                }, f, ensure_ascii=False)
            user_db.set_version("test-1", "1.0")
            with mkfile_utf8(os.path.join(
                    self.temp_dir, "test-2", "2.0", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({
                    "maintainer":
                        b"Unic\xc3\xb3de <unicode@example.org>".decode(
                            "UTF-8"),
                    "hooks": {"test1-app": {"new": "target-2"}},
                }, f, ensure_ascii=False)
            user_db.set_version("test-2", "2.0")
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            hook = Click.Hook.open(self.db, "new")
            hook.install()
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.new")
            self.assertTrue(os.path.lexists(path_1))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-1",
                    "target-1"),
                os.readlink(path_1))
            path_2 = os.path.join(self.temp_dir, "test-2_test1-app_2.0.new")
            self.assertTrue(os.path.lexists(path_2))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-2",
                    "target-2"),
                os.readlink(path_2))

            os.unlink(path_1)
            os.unlink(path_2)
            hook.install(user_name="another-user")
            self.assertFalse(os.path.lexists(path_1))
            self.assertFalse(os.path.lexists(path_2))

            hook.install(user_name="test-user")
            self.assertTrue(os.path.lexists(path_1))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-1",
                    "target-1"),
                os.readlink(path_1))
            self.assertTrue(os.path.lexists(path_2))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-2",
                    "target-2"),
                os.readlink(path_2))

    def test_remove(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            self._setup_hooks_dir(preloads)
            preloads["click_get_user_home"].return_value = "/home/test-user"
            with mkfile(os.path.join(self.temp_dir, "hooks", "old.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.old" % self.temp_dir, file=f)
            user_db = Click.User.for_user(self.db, "test-user")
            with mkfile(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({"hooks": {"test1-app": {"old": "target-1"}}}, f)
            user_db.set_version("test-1", "1.0")
            os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.old")
            os.symlink(
                os.path.join(user_db.get_path("test-1"), "target-1"), path_1)
            with mkfile(os.path.join(
                    self.temp_dir, "test-2", "2.0", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({"hooks": {"test2-app": {"old": "target-2"}}}, f)
            user_db.set_version("test-2", "2.0")
            path_2 = os.path.join(self.temp_dir, "test-2_test2-app_2.0.old")
            os.symlink(
                os.path.join(user_db.get_path("test-2"), "target-2"), path_2)
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            hook = Click.Hook.open(self.db, "old")
            hook.remove()
            self.assertFalse(os.path.exists(path_1))
            self.assertFalse(os.path.exists(path_2))

    def test_sync(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir", "click_get_user_home",
                ) as (enter, preloads):
            enter()
            preloads["click_get_user_home"].return_value = "/home/test-user"
            self._setup_hooks_dir(preloads)
            with mkfile(
                    os.path.join(self.temp_dir, "hooks", "test.hook")) as f:
                print("User-Level: yes", file=f)
                print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
            user_db = Click.User.for_user(self.db, "test-user")
            with mkfile(os.path.join(
                    self.temp_dir, "test-1", "1.0", ".click", "info",
                    "test-1.manifest")) as f:
                json.dump({"hooks": {"test1-app": {"test": "target-1"}}}, f)
            user_db.set_version("test-1", "1.0")
            with mkfile(os.path.join(
                    self.temp_dir, "test-2", "1.1", ".click", "info",
                    "test-2.manifest")) as f:
                json.dump({"hooks": {"test2-app": {"test": "target-2"}}}, f)
            user_db.set_version("test-2", "1.1")
            path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.test")
            os.symlink(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-1",
                    "target-1"),
                path_1)
            path_2 = os.path.join(self.temp_dir, "test-2_test2-app_1.1.test")
            path_3 = os.path.join(self.temp_dir, "test-3_test3-app_1.0.test")
            os.symlink(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-3",
                    "target-3"),
                path_3)
            self._setup_hooks_dir(
                preloads, hooks_dir=os.path.join(self.temp_dir, "hooks"))
            hook = Click.Hook.open(self.db, "test")
            hook.sync(user_name="test-user")
            self.assertTrue(os.path.lexists(path_1))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-1",
                    "target-1"),
                os.readlink(path_1))
            self.assertTrue(os.path.lexists(path_2))
            self.assertEqual(
                os.path.join(
                    self.temp_dir, ".click", "users", "test-user", "test-2",
                    "target-2"),
                os.readlink(path_2))
            self.assertFalse(os.path.lexists(path_3))


class TestPackageInstallHooks(TestClickHookBase):
    def test_removes_old_hooks(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            hooks_dir = os.path.join(self.temp_dir, "hooks")
            self._setup_hooks_dir(preloads, hooks_dir=hooks_dir)
            with mkfile(os.path.join(hooks_dir, "unity.hook")) as f:
                print("Pattern: %s/unity/${id}.scope" % self.temp_dir, file=f)
                print("Single-Version: yes", file=f)
            with mkfile(os.path.join(hooks_dir, "yelp-docs.hook")) as f:
                print("Pattern: %s/yelp/docs-${id}.txt" % self.temp_dir,
                      file=f)
                print("Single-Version: yes", file=f)
                print("Hook-Name: yelp", file=f)
            with mkfile(os.path.join(hooks_dir, "yelp-other.hook")) as f:
                print("Pattern: %s/yelp/other-${id}.txt" % self.temp_dir,
                      file=f)
                print("Single-Version: yes", file=f)
                print("Hook-Name: yelp", file=f)
            os.mkdir(os.path.join(self.temp_dir, "unity"))
            unity_path = os.path.join(
                self.temp_dir, "unity", "test_app_1.0.scope")
            os.symlink("dummy", unity_path)
            os.mkdir(os.path.join(self.temp_dir, "yelp"))
            yelp_docs_path = os.path.join(
                self.temp_dir, "yelp", "docs-test_app_1.0.txt")
            os.symlink("dummy", yelp_docs_path)
            yelp_other_path = os.path.join(
                self.temp_dir, "yelp", "other-test_app_1.0.txt")
            os.symlink("dummy", yelp_other_path)
            package_dir = os.path.join(self.temp_dir, "test")
            with mkfile(os.path.join(
                    package_dir, "1.0", ".click", "info",
                    "test.manifest")) as f:
                json.dump(
                    {"hooks": {"app": {"yelp": "foo.txt", "unity": "foo.scope"}}},
                    f)
            with mkfile(os.path.join(
                    package_dir, "1.1", ".click", "info",
                    "test.manifest")) as f:
                json.dump({}, f)
            Click.package_install_hooks(self.db, "test", "1.0", "1.1")
            self.assertFalse(os.path.lexists(unity_path))
            self.assertFalse(os.path.lexists(yelp_docs_path))
            self.assertFalse(os.path.lexists(yelp_other_path))

    def test_installs_new_hooks(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            hooks_dir = os.path.join(self.temp_dir, "hooks")
            self._setup_hooks_dir(preloads, hooks_dir=hooks_dir)
            with mkfile(os.path.join(hooks_dir, "a.hook")) as f:
                print("Pattern: %s/a/${id}.a" % self.temp_dir, file=f)
            with mkfile(os.path.join(hooks_dir, "b-1.hook")) as f:
                print("Pattern: %s/b/1-${id}.b" % self.temp_dir, file=f)
                print("Hook-Name: b", file=f)
            with mkfile(os.path.join(hooks_dir, "b-2.hook")) as f:
                print("Pattern: %s/b/2-${id}.b" % self.temp_dir, file=f)
                print("Hook-Name: b", file=f)
            os.mkdir(os.path.join(self.temp_dir, "a"))
            os.mkdir(os.path.join(self.temp_dir, "b"))
            package_dir = os.path.join(self.temp_dir, "test")
            with mkfile(os.path.join(
                    package_dir, "1.0", ".click", "info",
                    "test.manifest")) as f:
                json.dump({"hooks": {}}, f)
            with mkfile(os.path.join(
                    package_dir, "1.1", ".click", "info",
                    "test.manifest")) as f:
                json.dump({"hooks": {"app": {"a": "foo.a", "b": "foo.b"}}}, f)
            Click.package_install_hooks(self.db, "test", "1.0", "1.1")
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "a", "test_app_1.1.a")))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "b", "1-test_app_1.1.b")))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "b", "2-test_app_1.1.b")))

    def test_upgrades_existing_hooks(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            hooks_dir = os.path.join(self.temp_dir, "hooks")
            self._setup_hooks_dir(preloads, hooks_dir=hooks_dir)
            with mkfile(os.path.join(hooks_dir, "a.hook")) as f:
                print("Pattern: %s/a/${id}.a" % self.temp_dir, file=f)
                print("Single-Version: yes", file=f)
            with mkfile(os.path.join(hooks_dir, "b-1.hook")) as f:
                print("Pattern: %s/b/1-${id}.b" % self.temp_dir, file=f)
                print("Single-Version: yes", file=f)
                print("Hook-Name: b", file=f)
            with mkfile(os.path.join(hooks_dir, "b-2.hook")) as f:
                print("Pattern: %s/b/2-${id}.b" % self.temp_dir, file=f)
                print("Single-Version: yes", file=f)
                print("Hook-Name: b", file=f)
            with mkfile(os.path.join(hooks_dir, "c.hook")) as f:
                print("Pattern: %s/c/${id}.c" % self.temp_dir, file=f)
                print("Single-Version: yes", file=f)
            os.mkdir(os.path.join(self.temp_dir, "a"))
            a_path = os.path.join(self.temp_dir, "a", "test_app_1.0.a")
            os.symlink("dummy", a_path)
            os.mkdir(os.path.join(self.temp_dir, "b"))
            b_irrelevant_path = os.path.join(
                self.temp_dir, "b", "1-test_other-app_1.0.b")
            os.symlink("dummy", b_irrelevant_path)
            b_1_path = os.path.join(self.temp_dir, "b", "1-test_app_1.0.b")
            os.symlink("dummy", b_1_path)
            b_2_path = os.path.join(self.temp_dir, "b", "2-test_app_1.0.b")
            os.symlink("dummy", b_2_path)
            os.mkdir(os.path.join(self.temp_dir, "c"))
            package_dir = os.path.join(self.temp_dir, "test")
            with mkfile(os.path.join(
                    package_dir, "1.0", ".click", "info",
                    "test.manifest")) as f:
                json.dump({"hooks": {"app": {"a": "foo.a", "b": "foo.b"}}}, f)
            with mkfile(os.path.join(
                    package_dir, "1.1", ".click", "info",
                    "test.manifest")) as f:
                json.dump(
                    {"hooks": {
                        "app": {"a": "foo.a", "b": "foo.b", "c": "foo.c"}}
                    }, f)
            Click.package_install_hooks(self.db, "test", "1.0", "1.1")
            self.assertFalse(os.path.lexists(a_path))
            self.assertTrue(os.path.lexists(b_irrelevant_path))
            self.assertFalse(os.path.lexists(b_1_path))
            self.assertFalse(os.path.lexists(b_2_path))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "a", "test_app_1.1.a")))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "b", "1-test_app_1.1.b")))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "b", "2-test_app_1.1.b")))
            self.assertTrue(os.path.lexists(
                os.path.join(self.temp_dir, "c", "test_app_1.1.c")))


class TestPackageRemoveHooks(TestClickHookBase):
    def test_removes_hooks(self):
        with self.run_in_subprocess(
                "click_get_hooks_dir") as (enter, preloads):
            enter()
            hooks_dir = os.path.join(self.temp_dir, "hooks")
            self._setup_hooks_dir(preloads, hooks_dir=hooks_dir)
            with mkfile(os.path.join(hooks_dir, "unity.hook")) as f:
                print("Pattern: %s/unity/${id}.scope" % self.temp_dir, file=f)
            with mkfile(os.path.join(hooks_dir, "yelp-docs.hook")) as f:
                print("Pattern: %s/yelp/docs-${id}.txt" % self.temp_dir,
                      file=f)
                print("Hook-Name: yelp", file=f)
            with mkfile(os.path.join(hooks_dir, "yelp-other.hook")) as f:
                print("Pattern: %s/yelp/other-${id}.txt" % self.temp_dir,
                      file=f)
                print("Hook-Name: yelp", file=f)
            os.mkdir(os.path.join(self.temp_dir, "unity"))
            unity_path = os.path.join(
                self.temp_dir, "unity", "test_app_1.0.scope")
            os.symlink("dummy", unity_path)
            os.mkdir(os.path.join(self.temp_dir, "yelp"))
            yelp_docs_path = os.path.join(
                self.temp_dir, "yelp", "docs-test_app_1.0.txt")
            os.symlink("dummy", yelp_docs_path)
            yelp_other_path = os.path.join(
                self.temp_dir, "yelp", "other-test_app_1.0.txt")
            os.symlink("dummy", yelp_other_path)
            package_dir = os.path.join(self.temp_dir, "test")
            with mkfile(os.path.join(
                    package_dir, "1.0", ".click", "info",
                    "test.manifest")) as f:
                json.dump(
                    {"hooks": {
                        "app": {"yelp": "foo.txt", "unity": "foo.scope"}}
                    }, f)
            Click.package_remove_hooks(self.db, "test", "1.0")
            self.assertFalse(os.path.lexists(unity_path))
            self.assertFalse(os.path.lexists(yelp_docs_path))
            self.assertFalse(os.path.lexists(yelp_other_path))
