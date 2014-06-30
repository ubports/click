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

import json
import os
import shutil
import subprocess
import unittest

from .helpers import chdir, TestCase


@unittest.skipIf(
    os.getuid() != 0, "This tests needs to run as root")
@unittest.skipIf(
    subprocess.call(
        ["ping", "-c1", "archive.ubuntu.com"]) != 0, "Need network")
class TestBuildCoreApps(TestCase):

    TEST_BUILD_BRANCHES = ["lp:camera-app",
                           "lp:notes-app",
                          ]

    def _run_in_chroot(self, cmd):
        return subprocess.check_call([
            self.click_binary, "chroot", 
            "-a", self.arch, "-f", self.framework, "run"] + cmd)

    def _configure(self):
        self._run_in_chroot(
            ["cmake", ".", "-DCLICK_MODE=on", "-DINSTALL_TESTS=off"])

    def _make(self):
        self.assertEqual(self._run_in_chroot(
            ["make", "DESTDIR=package", "install"]), 0)

    def _build_click(self):
        subprocess.check_call(
            [self.click_binary, "build", "package"])

    def _find_manifest(self, start_dir):
        for path, dirs, files in os.walk(start_dir):
            for needle in ["manifest.json", "manifest.json.in"]:
                if needle in files:
                    return os.path.join(path, needle)
        return None

    def _set_arch_and_framework_from_manifest(self, manifest):
        with open(manifest) as f:
            data = json.load(f)
        self.arch = data["architecture"]
        self.framework = data["framework"]
        # ?!?
        self.framework = self.framework.rsplit("-", maxsplit=1)[0]

    def _ensure_click_chroot(self):
        # FIXME: once there is a "click chroot list" we can skip this
        subprocess.call([
            self.click_binary,
            "chroot",
             "-a", self.arch,
             "-f", self.framework,
             "create"])
        # bug #1316930(?)
        subprocess.call([
            self.click_binary,
            "chroot",
            "-a", self.arch,
            "-f", self.framework,
            "maint",
            "apt-get", "install", "-y", "python3",
        ])

    def test_build_core_apps(self):
        for branch in self.TEST_BUILD_BRANCHES:
            # get and parse
            branch_dir = branch[len("lp:"):]
            # always use a fresh checkout
            if os.path.exists(branch_dir):
                shutil.rmtree(branch_dir)
            subprocess.check_call(["bzr","branch", branch])
            manifest = self._find_manifest(branch_dir)
            # build it
            self._set_arch_and_framework_from_manifest(manifest)
            with chdir(branch_dir):
                self._ensure_click_chroot()
                self._configure()
                self._make()
                self._build_click()
                

                
