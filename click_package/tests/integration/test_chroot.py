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

import subprocess
import unittest

from .helpers import (
    require_network,
    require_root,
    ClickTestCase,
)

# architectures present in 14.04 (current default framework)
ALLOW_ARCHITECTURES = [
    "amd64", "arm64", "armhf", "i386", "powerpc", "ppc64el"]


def skipUnlessAllowedArchitecture():
    system_arch = subprocess.check_output(
        ["dpkg", "--print-architecture"], universal_newlines=True).strip()
    if system_arch in ALLOW_ARCHITECTURES:
        return lambda func: func
    else:
        return unittest.skip("%s does not exist in 14.04")


@skipUnlessAllowedArchitecture()
class TestChroot(ClickTestCase):

    @classmethod
    def command(cls, arch, *args):
        return [cls.click_binary, "chroot", "-a", arch] + list(args)

    @classmethod
    def setUpClass(cls):
        super(TestChroot, cls).setUpClass()
        require_root()
        require_network()
        cls.arch = subprocess.check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True).strip()
        subprocess.check_call(cls.command(cls.arch, "create"))

    @classmethod
    def tearDownClass(cls):
        subprocess.check_call(cls.command(cls.arch, "destroy"))

    def test_upgrade(self):
        subprocess.check_call(self.command(self.arch, "upgrade"))

    def test_install(self):
        subprocess.check_call(self.command(self.arch, "install", "apt-utils"))

    def test_run(self):
        output = subprocess.check_output(
            self.command(self.arch, "run", "echo", "hello world"),
            universal_newlines=True)
        self.assertEqual(output, "hello world\n")

    def test_maint(self):
        output = subprocess.check_output(
            self.command(self.arch, "maint", "id"),
            universal_newlines=True)
        self.assertEqual(output, "uid=0(root) gid=0(root) groups=0(root)\n")

    def test_exists_ok(self):
        subprocess.check_call(self.command(self.arch, "exists"))

    def test_exists_no(self):
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(
                self.command("arch-that-does-not-exist", "exists"))


class TestChrootName(TestChroot):
    """Run the chroot tests again with a different --name."""

    @classmethod
    def command(cls, arch, *args):
        return super(TestChrootName, cls).command(
            arch, "-n", "testname", *args)

    def test_exists_different_name_fails(self):
        # "click chroot exists" fails for a non-existent name.
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.check_call(super(TestChrootName, self).command(
                self.arch, "-n", "testname2", "exists"))
