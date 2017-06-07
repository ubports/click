# Copyright (C) 2014 Canonical Ltd.
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

"""Unit tests for click_package.framework."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestClickFramework',
    ]


import os

from gi.repository import Click

from click_package.tests.helpers import TestCase, touch


class TestClickFramework(TestCase):
    def setUp(self):
        super(TestClickFramework, self).setUp()
        self.use_temp_dir()

    def _setup_frameworks(self, preloads, frameworks_dir=None, frameworks={}):
        if frameworks_dir is None:
            frameworks_dir = os.path.join(self.temp_dir, "frameworks")
        Click.ensuredir(frameworks_dir)
        for framework_name in frameworks:
            framework_path = os.path.join(
                frameworks_dir, "%s.framework" % framework_name)
            with open(framework_path, "w") as framework:
                for key, value in frameworks[framework_name].items():
                    print("%s: %s" % (key, value), file=framework)
        preloads["click_get_frameworks_dir"].side_effect = (
            lambda: self.make_string(frameworks_dir))

    def test_open(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            self._setup_frameworks(preloads, frameworks={"framework-1": {}})
            Click.Framework.open("framework-1")
            self.assertRaisesFrameworkError(
                Click.FrameworkError.NO_SUCH_FRAMEWORK,
                Click.Framework.open, "framework-2")

    def test_has_framework(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            self._setup_frameworks(preloads, frameworks={"framework-1": {}})
            self.assertTrue(Click.Framework.has_framework("framework-1"))
            self.assertFalse(Click.Framework.has_framework("framework-2"))

    def test_get_frameworks(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            self._setup_frameworks(
                preloads,
                frameworks={"ubuntu-sdk-13.10": {}, "ubuntu-sdk-14.04": {},
                            "ubuntu-sdk-14.10": {}})
            self.assertEqual(
                ["ubuntu-sdk-13.10", "ubuntu-sdk-14.04", "ubuntu-sdk-14.10"],
                sorted(f.props.name for f in Click.Framework.get_frameworks()))

    def test_get_frameworks_nonexistent(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            frameworks_dir = os.path.join(self.temp_dir, "nonexistent")
            preloads["click_get_frameworks_dir"].side_effect = (
                lambda: self.make_string(frameworks_dir))
            self.assertEqual([], Click.Framework.get_frameworks())

    def test_get_frameworks_not_directory(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = os.path.join(self.temp_dir, "file")
            touch(path)
            preloads["click_get_frameworks_dir"].side_effect = (
                lambda: self.make_string(path))
            self.assertEqual([], Click.Framework.get_frameworks())

    def test_get_frameworks_ignores_other_files(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            frameworks_dir = os.path.join(self.temp_dir, "frameworks")
            Click.ensuredir(frameworks_dir)
            touch(os.path.join(frameworks_dir, "file"))
            preloads["click_get_frameworks_dir"].side_effect = (
                lambda: self.make_string(frameworks_dir))
            self.assertEqual([], Click.Framework.get_frameworks())

    def test_get_frameworks_ignores_unopenable_files(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            frameworks_dir = os.path.join(self.temp_dir, "frameworks")
            Click.ensuredir(frameworks_dir)
            os.symlink(
                "nonexistent", os.path.join(frameworks_dir, "foo.framework"))
            preloads["click_get_frameworks_dir"].side_effect = (
                lambda: self.make_string(frameworks_dir))
            self.assertEqual([], Click.Framework.get_frameworks())

    def test_fields(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            self._setup_frameworks(
                preloads,
                frameworks={
                    "ubuntu-sdk-14.04-qml": {
                        "base-name": "ubuntu-sdk", "base-version": "14.04",
                    }})
            framework = Click.Framework.open("ubuntu-sdk-14.04-qml")
            self.assertCountEqual(
                ["base-name", "base-version"], framework.get_fields())
            self.assertEqual("ubuntu-sdk", framework.get_field("base-name"))
            self.assertEqual("14.04", framework.get_field("base-version"))
            self.assertRaisesFrameworkError(
                Click.FrameworkError.MISSING_FIELD,
                framework.get_field, "nonexistent")
            self.assertEqual("ubuntu-sdk", framework.get_base_name())
            self.assertEqual("14.04", framework.get_base_version())
