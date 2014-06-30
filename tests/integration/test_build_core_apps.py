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

"""Integration tests for the click chroot feature."""

import os
import subprocess
import unittest

from .helpers import chdir, TestCase

@unittest.skipIf(
    os.getuid() != 0, "This tests needs to run as root")
@unittest.skipIf(
    subprocess.call(
        ["ping", "-c1", "archive.ubuntu.com"]) != 0, "Need network")
class TestBuildCoreApps(TestCase):

    ARCH = "armhf"
    FRAMEWORK = "ubuntu-sdk-14.04"
    TEST_BUILD_BRANCHES = ["lp:ubuntu-filemanager-app",
                          ]

    @classmethod
    def setUpClass(cls):
        super(TestBuildCoreApps, cls).setUpClass()
        subprocess.check_call([
            cls.click_binary,
            "chroot",
            "-a", cls.ARCH,
            "-f", cls.FRAMEWORK,
            "create"])

    @classmethod
    def tearDownClass(cls):
        return subprocess.check_call([
            cls.click_binary,
            "chroot", "-a", cls.ARCH,
            "destroy"])

    def _run_in_chroot(self, cmd):
        return subprocess.check_call([
            self.click_binary, "chroot", 
            "-a", self.ARCH, "-f", self.FRAMEWORK, "run"] + cmd)

    def test_build(self):
        for branch in self.TEST_BUILD_BRANCHES:
            self._run_in_chroot(["bzr","branch", branch])
            with chdir(branch[len("lp:"):]):
                self.assertEqual(self._run_in_chroot(["cmake", "."]), 0)
                self.assertEqual(self._run_in_chroot(["make"]), 0)

                
