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

"""Unit tests for clickpackage.hooks."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "TestClickHook",
    ]


import contextlib
import json
import os
from textwrap import dedent

try:
    from unittest import mock
except ImportError:
    import mock

from clickpackage import hooks
from clickpackage.hooks import ClickHook, run_hooks
from clickpackage.tests.helpers import TestCase, mkfile


@contextlib.contextmanager
def temp_hooks_dir(new_dir):
    old_dir = hooks.HOOKS_DIR
    try:
        hooks.HOOKS_DIR = new_dir
        yield
    finally:
        hooks.HOOKS_DIR = old_dir


class TestClickHook(TestCase):
    def setUp(self):
        super(TestClickHook, self).setUp()
        self.use_temp_dir()

    def test_open(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print(dedent("""\
                Pattern: /usr/share/test/%s.test
                # Comment
                Exec: test-update
                """), file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        self.assertCountEqual(["Pattern", "Exec"], hook.keys())
        self.assertEqual("/usr/share/test/%s.test", hook["pattern"])
        self.assertEqual("test-update", hook["exec"])

    @mock.patch("subprocess.check_call")
    def test_run_commands(self, mock_check_call):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Exec: test-update", file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook._run_commands()
        mock_check_call.assert_called_once_with("test-update", shell=True)

    def test_install(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/%%s.test" % self.temp_dir, file=f)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(self.temp_dir, "org.example.package", "1.0", "foo/bar")
        symlink_path = os.path.join(self.temp_dir, "org.example.package.test")
        target_path = os.path.join(
            self.temp_dir, "org.example.package", "1.0", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    def test_upgrade(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/%%s.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(self.temp_dir, "org.example.package.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.install(self.temp_dir, "org.example.package", "1.0", "foo/bar")
        target_path = os.path.join(
            self.temp_dir, "org.example.package", "1.0", "foo", "bar")
        self.assertTrue(os.path.islink(symlink_path))
        self.assertEqual(target_path, os.readlink(symlink_path))

    def test_remove(self):
        with mkfile(os.path.join(self.temp_dir, "test.hook")) as f:
            print("Pattern: %s/%%s.test" % self.temp_dir, file=f)
        symlink_path = os.path.join(self.temp_dir, "org.example.package.test")
        os.symlink("old-target", symlink_path)
        with temp_hooks_dir(self.temp_dir):
            hook = ClickHook.open("test")
        hook.remove("org.example.package")
        self.assertFalse(os.path.exists(symlink_path))


class TestRunHooks(TestCase):
    def setUp(self):
        super(TestRunHooks, self).setUp()
        self.use_temp_dir()

    @mock.patch("clickpackage.hooks.ClickHook.open")
    def test_removes_old_hooks(self, mock_open):
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(package_dir, "1.0", "manifest.json")) as f:
            f.write(json.dumps(
                {"hooks": {"yelp": "foo.txt", "unity": "foo.scope"}}))
        with mkfile(os.path.join(package_dir, "1.1", "manifest.json")) as f:
            f.write(json.dumps({}))
        run_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(2, mock_open.call_count)
        mock_open.assert_has_calls([
            mock.call("unity"),
            mock.call().remove("test"),
            mock.call("yelp"),
            mock.call().remove("test"),
        ])

    @mock.patch("clickpackage.hooks.ClickHook.open")
    def test_installs_new_hooks(self, mock_open):
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(package_dir, "1.0", "manifest.json")) as f:
            f.write(json.dumps({"hooks": {}}))
        with mkfile(os.path.join(package_dir, "1.1", "manifest.json")) as f:
            f.write(json.dumps({"hooks": {"a": "foo.a", "b": "foo.b"}}))
        run_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(2, mock_open.call_count)
        mock_open.assert_has_calls([
            mock.call("a"),
            mock.call().install(self.temp_dir, "test", "1.1", "foo.a"),
            mock.call("b"),
            mock.call().install(self.temp_dir, "test", "1.1", "foo.b"),
        ])

    @mock.patch("clickpackage.hooks.ClickHook.open")
    def test_upgrades_existing_hooks(self, mock_open):
        package_dir = os.path.join(self.temp_dir, "test")
        with mkfile(os.path.join(package_dir, "1.0", "manifest.json")) as f:
            f.write(json.dumps({"hooks": {"a": "foo.a", "b": "foo.b"}}))
        with mkfile(os.path.join(package_dir, "1.1", "manifest.json")) as f:
            f.write(json.dumps(
                {"hooks": {"a": "foo.a", "b": "foo.b", "c": "foo.c"}}))
        run_hooks(self.temp_dir, "test", "1.0", "1.1")
        self.assertEqual(3, mock_open.call_count)
        mock_open.assert_has_calls([
            mock.call("a"),
            mock.call().install(self.temp_dir, "test", "1.1", "foo.a"),
            mock.call("b"),
            mock.call().install(self.temp_dir, "test", "1.1", "foo.b"),
        ])
