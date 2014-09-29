# Copyright (C) 2014 Canonical Ltd.
# Author: Michael Vogt <michael.vogt@ubuntu.com>

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

"""Integration tests for the click CLI info command."""

import json
import os
import subprocess

from .helpers import ClickTestCase


class TestInfo(ClickTestCase):
    def test_info_from_path(self):
        name = "com.example.foo"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "info", path_to_click], universal_newlines=True)
        self.assertEqual(name, json.loads(output)["name"])


    def test_info_installed_click(self):
        name = "com.example.foo"
        user = os.environ.get("USER", "root")
        path_to_click = self._make_click(name, framework="")
        self.click_install(path_to_click, name, user)
        output = subprocess.check_output([
            self.click_binary, "info", name], universal_newlines=True)
        self.assertEqual(json.loads(output)["name"], name)

    def test_info_file_in_package(self):
        name = "org.example.info"
        version = "1.0"
        click_pkg = self._make_click(name=name, version=version, framework="")
        subprocess.check_call(
            [self.click_binary, "install", "--allow-unauthenticated",
             "--all-users", click_pkg])
        self.addCleanup(
            subprocess.check_call,
            [self.click_binary, "unregister", "--all-users", name])
        output = subprocess.check_output(
            [self.click_binary, "info",
             "/opt/click.ubuntu.com/%s/%s/README" % (name, version)],
            universal_newlines=True)
        self.assertEqual(name, json.loads(output)["name"])
