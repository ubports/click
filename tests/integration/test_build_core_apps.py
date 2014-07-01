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

from glob import glob
import json
import os
import shutil
import subprocess
import unittest

from .helpers import (
    chdir,
    has_network,
    is_root,
    TestCase,
)

# the branches we want to testbuild
TEST_BUILD_BRANCHES = [
    "lp:camera-app",
    "lp:notes-app",
]

# command to "configure"
CORE_APP_CONFIGURE_CMD  = [
    "cmake", "..", "-DCLICK_MODE=on", "-DINSTALL_TESTS=off"]

# command to make install
CLICK_TARGET_DIR = "click-package"
CORE_APP_MAKE_CMD = [
    "make", "DESTDIR=%s" % CLICK_TARGET_DIR, "install"]


def find_manifest(start_dir):
    """Find a click manifest.json{,.in} under the given directory"""
    for path, dirs, files in os.walk(start_dir):
        for needle in ["manifest.json", "manifest.json.in"]:
            if needle in files:
                return os.path.join(path, needle)
    return None


@unittest.skipIf(not is_root(), "This tests needs to run as root")
@unittest.skipIf(not has_network(), "Need network")
class TestBuildCoreApps(TestCase):

    def _run_in_chroot(self, cmd):
        """Run the given cmd in a click chroot"""
        return subprocess.check_call(self.chroot_cmd + ["run"] + cmd)

    def _set_arch_and_framework_from_manifest(self, manifest):
        with open(manifest) as f:
            data = json.load(f)
        self.arch = data["architecture"]
        self.framework = data["framework"]
        # ?!? the framework can be in the form "ubuntu-sdk-14.04-dev2"
        #     but chroot expects "ubuntu-sdk-14.04" (without the -dev suffix)
        if "-dev" in self.framework:
            self.framework = self.framework.rsplit("-", maxsplit=1)[0]

    @property
    def chroot_cmd(self):
        return [
            self.click_binary, "chroot", "-a", self.arch, "-f", self.framework]

    def _ensure_click_chroot(self):
        if subprocess.call(self.chroot_cmd + ["exists"]) != 0:
            subprocess.check_call(self.chroot_cmd + ["create"])

    def configure(self):
        self._run_in_chroot(CORE_APP_CONFIGURE_CMD)

    def make(self):
        self._run_in_chroot(CORE_APP_MAKE_CMD)

    def create_click(self):
        subprocess.check_call(
            [self.click_binary, "build", CLICK_TARGET_DIR])
        # we expect exactly one click
        self.assertEqual(len(glob("*.click")), 1)

    def test_build_core_apps(self):
        for branch in TEST_BUILD_BRANCHES:
            # get and parse
            branch_dir = branch[len("lp:"):]
            build_dir = os.path.join(branch_dir, "build-tree")
            if os.path.exists(branch_dir):
                subprocess.check_call(["bzr","pull"], cwd=branch_dir)
            else:
                subprocess.check_call(["bzr","branch", branch])
            manifest = find_manifest(branch_dir)
            # build it
            self._set_arch_and_framework_from_manifest(manifest)
            if os.path.exists(build_dir):
                shutil.rmtree(build_dir)
            os.makedirs(build_dir)
            with chdir(build_dir):
                self._ensure_click_chroot()
                self.configure()
                self.make()
                self.create_click()
                

                
