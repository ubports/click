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

from .helpers import TestCase

@unittest.skipIf(
    os.getuid() != 0, "This tests needs to run as root")
@unittest.skipIf(
    subprocess.call(
        ["ping", "-c1", "archive.ubuntu.com"]) != 0, "Need network")
class TestChroot(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestChroot, cls).setUpClass()
        cls.arch = subprocess.check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True).strip()
        subprocess.check_call([
            cls.click_binary,
            "chroot", "-a", cls.arch,
            "create"])

    @classmethod
    def tearDownClass(cls):
        subprocess.check_call([
            cls.click_binary,
            "chroot", "-a", cls.arch,
            "destroy"])

    def test_upgrade(self):
        subprocess.check_call([
            self.click_binary, "chroot", "-a", self.arch,
            "upgrade"])

    def test_install(self):
        subprocess.check_call([
            self.click_binary, "chroot", "-a", self.arch,
            "install", "apt-utils"])

    def test_run(self):
        output = subprocess.check_output([
            self.click_binary, "chroot", "-a", self.arch,
            "run", "echo", "hello world"], universal_newlines=True)
        self.assertEqual(output, "hello world\n")

    def test_maint(self):
        output = subprocess.check_output([
            self.click_binary, "chroot", "-a", self.arch,
            "maint", "id"], universal_newlines=True)
        self.assertEqual(output, "uid=0(root) gid=0(root) groups=0(root)\n")
