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
    ]


import contextlib
import json
import os
from textwrap import dedent

from click import hooks
from click.hooks import ClickHook, ClickPatternFormatter, package_install_hooks
from click.user import ClickUser
from click.tests.helpers import TestCase, mkfile, mock


@contextlib.contextmanager
def temp_hooks_dir(new_dir):
    old_dir = hooks.hooks_dir
    try:
        hooks.hooks_dir = new_dir
        yield
    finally:
        hooks.hooks_dir = old_dir


class TestClickPatternFormatter(TestCase):
    def setUp(self):
        super(TestClickPatternFormatter, self).setUp()
        self.formatter = ClickPatternFormatter()

    def test_expands_provided_keys(self):
        self.assertEqual(
            "foo.bar", self.formatter.format("foo.${key}", key="bar"))
        self.assertEqual(
            "foo.barbaz",
            self.formatter.format(
                "foo.${key1}${key2}", key1="bar", key2="baz"))

    def test_expands_missing_keys_to_empty_string(self):
        self.assertEqual("xy", self.formatter.format("x${key}y"))

    def test_preserves_unmatched_dollar(self):
        self.assertEqual("$", self.formatter.format("$"))
        self.assertEqual("$ {foo}", self.formatter.format("$ {foo}"))
        self.assertEqual("x${y", self.formatter.format("${key}${y", key="x"))


class TestClickHookSystemLevel(TestCase):
    def setUp(self):
        super(TestClickHookSystemLevel, self).setUp()
        self.use_temp_dir()

    def test_open(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print(dedent("""\
                Pattern: /usr/share/test/${id}.test
                # Comment
                Exec: test-update
                User: root
                """), file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertCountEqual(["Pattern", "Exec", "User"], hook.keys())
        self.assertEqual("/usr/share/test/${id}.test", hook["pattern"])
        self.assertEqual("test-update", hook["exec"])
        self.assertFalse(hook.user_level)

    def test_invalid_app_id(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print(dedent("""\
                Pattern: /usr/share/test/${id}.test
                # Comment
                Exec: test-update
                User: root
                """), file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertRaises(
            ValueError, hook.app_id, "package", "0.1", "app_name")
        self.assertRaises(
            ValueError, hook.app_id, "package", "0.1", "app/name")

    @mock.patch("subprocess.check_call")
    def test_run_commands(self, mock_check_call):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Exec: test-update", file=f)
            print("User: root", file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertEqual("root", hook._run_commands_user(user=None))
        hook._run_commands(user=None)
        mock_check_call.assert_called_once_with(
            "test-update", preexec_fn=mock.ANY, shell=True)

    def test_install(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(
            self.temp_dir, "org.example.package", "1.0", "test-app", "foo/bar")
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        target_path = os.path.join(
            self.temp_dir, "org.example.package", "1.0", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    def test_upgrade(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(
            self.temp_dir, "org.example.package", "1.0", "test-app", "foo/bar")
        target_path = os.path.join(
            self.temp_dir, "org.example.package", "1.0", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    def test_remove(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.remove("org.example.package", "1.0", "test-app")
        self.assertFalse(os.path.exists(symlink_path))

    def test_install_all(self):
        with mkfile(os.path.join(self.temp_dir, "hooks", "new.hook")) as f:
            print("Pattern: %s/${id}.new" % self.temp_dir, file=f)
        with mkfile(os.path.join(
                self.temp_dir, "test-1", "1.0", ".click", "info",
                "test-1.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"new": "target-1"}}}))
        os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
        with mkfile(os.path.join(
                self.temp_dir, "test-2", "2.0", ".click", "info",
                "test-2.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"new": "target-2"}}}))
        os.symlink("2.0", os.path.join(self.temp_dir, "test-2", "current"))
        with temp_hooks_dir(os.path.join(self.temp_dir, "hooks")):
            hook = ClickHook.open("new")
        hook.install_all(self.temp_dir)
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

    def test_remove_all(self):
        with mkfile(os.path.join(self.temp_dir, "hooks", "old.hook")) as f:
            print("Pattern: %s/${id}.old" % self.temp_dir, file=f)
        with mkfile(os.path.join(
                self.temp_dir, "test-1", "1.0", ".click", "info",
                "test-1.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"old": "target-1"}}}))
        os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
        path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.old")
        os.symlink(
            os.path.join(self.temp_dir, "test-1", "1.0", "target-1"), path_1)
        with mkfile(os.path.join(
                self.temp_dir, "test-2", "2.0", ".click", "info",
                "test-2.manifest")) as f:
            f.write(json.dumps({"hooks": {"test2-app": {"old": "target-2"}}}))
        os.symlink("2.0", os.path.join(self.temp_dir, "test-2", "current"))
        path_2 = os.path.join(self.temp_dir, "test-2_test2-app_2.0.old")
        os.symlink(
            os.path.join(self.temp_dir, "test-2", "2.0", "target-2"), path_2)
        with temp_hooks_dir(os.path.join(self.temp_dir, "hooks")):
            hook = ClickHook.open("old")
        hook.remove_all(self.temp_dir)
        self.assertFalse(os.path.exists(path_1))
        self.assertFalse(os.path.exists(path_2))


class TestClickHookUserLevel(TestCase):
    def setUp(self):
        super(TestClickHookUserLevel, self).setUp()
        self.use_temp_dir()

    def test_open(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print(dedent("""\
                User-Level: yes
                Pattern: ${home}/.local/share/test/${id}.test
                # Comment
                Exec: test-update
                """), file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertCountEqual(["User-Level", "Pattern", "Exec"], hook.keys())
        self.assertEqual(
            "${home}/.local/share/test/${id}.test", hook["pattern"])
        self.assertEqual("test-update", hook["exec"])
        self.assertTrue(hook.user_level)

    def test_invalid_app_id(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print(dedent("""\
                User-Level: yes
                Pattern: ${home}/.local/share/test/${id}.test
                # Comment
                Exec: test-update
                """), file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertRaises(
            ValueError, hook.app_id, "package", "0.1", "app_name")
        self.assertRaises(
            ValueError, hook.app_id, "package", "0.1", "app/name")

    @mock.patch("subprocess.check_call")
    def test_run_commands(self, mock_check_call):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("User-Level: yes", file=f)
            print("Exec: test-update", file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertEqual(
            "test-user", hook._run_commands_user(user="test-user"))
        hook._run_commands(user="test-user")
        mock_check_call.assert_called_once_with(
            "test-update", preexec_fn=mock.ANY, shell=True)

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_install(self, *args):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(
            self.temp_dir, "org.example.package", "1.0", "test-app", "foo/bar",
            user="test-user")
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        target_path = os.path.join(
            self.temp_dir, ".click", "users", "test-user",
            "org.example.package", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_install_removes_previous(self, *args):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(
            self.temp_dir, "org.example.package", "1.0", "test-app", "foo/bar",
            user="test-user")
        hook.install(
            self.temp_dir, "org.example.package", "1.1", "test-app", "foo/bar",
            user="test-user")
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

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_upgrade(self, *args):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(
            self.temp_dir, "org.example.package", "1.0", "test-app", "foo/bar",
            user="test-user")
        target_path = os.path.join(
            self.temp_dir, ".click", "users", "test-user",
            "org.example.package", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_remove(self, *args):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(
            self.temp_dir, "org.example.package_test-app_1.0.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.remove("org.example.package", "1.0", "test-app", user="test-user")
        self.assertFalse(os.path.exists(symlink_path))

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_install_all(self, *args):
        with mkfile(os.path.join(self.temp_dir, "hooks", "new.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.new" % self.temp_dir, file=f)
        user_db = ClickUser(self.temp_dir, user="test-user")
        with mkfile(os.path.join(
                self.temp_dir, "test-1", "1.0", ".click", "info",
                "test-1.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"new": "target-1"}}}))
        user_db["test-1"] = "1.0"
        with mkfile(os.path.join(
                self.temp_dir, "test-2", "2.0", ".click", "info",
                "test-2.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"new": "target-2"}}}))
        user_db["test-2"] = "2.0"
        with temp_hooks_dir(os.path.join(self.temp_dir, "hooks")):
            hook = ClickHook.open("new")
        hook.install_all(self.temp_dir)
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

    @mock.patch(
        "click.hooks.ClickHook._user_home", return_value="/home/test-user")
    def test_remove_all(self, *args):
        with mkfile(os.path.join(self.temp_dir, "hooks", "old.hook")) as f:
            print("User-Level: yes", file=f)
            print("Pattern: %s/${id}.old" % self.temp_dir, file=f)
        user_db = ClickUser(self.temp_dir, user="test-user")
        with mkfile(os.path.join(
                self.temp_dir, "test-1", "1.0", ".click", "info",
                "test-1.manifest")) as f:
            f.write(json.dumps({"hooks": {"test1-app": {"old": "target-1"}}}))
        user_db["test-1"] = "1.0"
        os.symlink("1.0", os.path.join(self.temp_dir, "test-1", "current"))
        path_1 = os.path.join(self.temp_dir, "test-1_test1-app_1.0.old")
        os.symlink(os.path.join(user_db.path("test-1"), "target-1"), path_1)
        with mkfile(os.path.join(
                self.temp_dir, "test-2", "2.0", ".click", "info",
                "test-2.manifest")) as f:
            f.write(json.dumps({"hooks": {"test2-app": {"old": "target-2"}}}))
        user_db["test-2"] = "2.0"
        path_2 = os.path.join(self.temp_dir, "test-2_test2-app_2.0.old")
        os.symlink(os.path.join(user_db.path("test-2"), "target-2"), path_2)
        with temp_hooks_dir(os.path.join(self.temp_dir, "hooks")):
            hook = ClickHook.open("old")
        hook.remove_all(self.temp_dir)
        self.assertFalse(os.path.exists(path_1))
        self.assertFalse(os.path.exists(path_2))


class TestPackageInstallHooks(TestCase):
    def setUp(self):
        super(TestPackageInstallHooks, self).setUp()
        self.use_temp_dir()

    def assert_has_calls_sparse(self, mock_obj, calls):
        """Like mock.assert_has_calls, but allows other calls in between."""
        expected_calls = list(calls)
        for call in mock_obj.mock_calls:
            if not expected_calls:
                return
            if call == expected_calls[0]:
                expected_calls.pop(0)
        if expected_calls:
            raise AssertionError(
                "Calls not found.\nExpected: %r\nActual: %r" %
                (calls, mock_obj.mock_calls))

    @mock.patch("click.hooks.ClickHook.open")
    def test_removes_old_hooks(self, mock_open):
        mock_open.return_value.user_level = False
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(
                package_dir, "1.0", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps(
                {"hooks": {"app": {"yelp": "foo.txt", "unity": "foo.scope"}}}))
        with mkfile(os.path.join(
                package_dir, "1.1", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps({}))
        package_install_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(2, mock_open.call_count)
        self.assert_has_calls_sparse(mock_open, [
            mock.call("unity"),
            mock.call().remove("test", "1.0", "app", user=None),
            mock.call("yelp"),
            mock.call().remove("test", "1.0", "app", user=None),
        ])

    @mock.patch("click.hooks.ClickHook.open")
    def test_installs_new_hooks(self, mock_open):
        mock_open.return_value.user_level = False
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(
                package_dir, "1.0", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps({"hooks": {}}))
        with mkfile(os.path.join(
                package_dir, "1.1", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps(
                {"hooks": {"app": {"a": "foo.a", "b": "foo.b"}}}))
        package_install_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(2, mock_open.call_count)
        self.assert_has_calls_sparse(mock_open, [
            mock.call("a"),
            mock.call().install(
                self.temp_dir, "test", "1.1", "app", "foo.a", user=None),
            mock.call("b"),
            mock.call().install(
                self.temp_dir, "test", "1.1", "app", "foo.b", user=None),
        ])

    @mock.patch("click.hooks.ClickHook.open")
    def test_upgrades_existing_hooks(self, mock_open):
        mock_open.return_value.user_level = False
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(
                package_dir, "1.0", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps(
                {"hooks": {"app": {"a": "foo.a", "b": "foo.b"}}}))
        with mkfile(os.path.join(
                package_dir, "1.1", ".click", "info", "test.manifest")) as f:
            f.write(json.dumps(
                {"hooks": {
                    "app": {"a": "foo.a", "b": "foo.b", "c": "foo.c"}}
                }))
        package_install_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(3, mock_open.call_count)
        self.assert_has_calls_sparse(mock_open, [
            mock.call("a"),
            mock.call().install(
                self.temp_dir, "test", "1.1", "app", "foo.a", user=None),
            mock.call("b"),
            mock.call().install(
                self.temp_dir, "test", "1.1", "app", "foo.b", user=None),
            mock.call("c"),
            mock.call().install(
                self.temp_dir, "test", "1.1", "app", "foo.c", user=None),
        ])
