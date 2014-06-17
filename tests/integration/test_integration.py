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

"""Integration tests for the click CLI interface."""

import json
import os
import re
import subprocess
import unittest

from .helpers import TestCase


class TestBuild(TestCase):
    def test_build(self):
        path_to_click = self._make_click()
        self.assertTrue(os.path.exists(path_to_click))


class TestInfo(TestCase):
    def test_info(self):
        name = "com.ubuntu.foo"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "info", path_to_click], universal_newlines=True)
        self.assertEqual(json.loads(output)["name"], name)


class TestVerify(TestCase):
    def test_verify_ok(self):
        name = "com.ubuntu.verify-ok"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "verify", "--force-missing-framework",
            path_to_click], universal_newlines=True)
        self.assertEqual(output, "")


class TestContents(TestCase):
    def test_contents(self):
        name = "com.ubuntu.contents"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "contents", path_to_click],
            universal_newlines=True)
        self.assertTrue(re.search(
            r'-rw-r[-w]-r-- root/root\s+[0-9]+\s+[0-9-]+ [0-9:]+ ./README', output))

@unittest.skipIf(
    (not os.path.exists("/usr/share/click/frameworks") or 
     not os.listdir("/usr/share/click/frameworks")),
    "Please install ubuntu-sdk-libs")
class TestFrameworks(TestCase):
    def test_framework_list(self):
        output = subprocess.check_output([
            self.click_binary, "framework", "list"], universal_newlines=True)
        self.assertTrue("ubuntu-sdk-" in output)
