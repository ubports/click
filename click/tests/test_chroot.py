# Copyright (C) 2014 Canonical Ltd.
# Author: Michael Vogt

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

"""Unit tests for click.chroot."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestClickChroot',
    ]

from mock import patch
import os
from textwrap import dedent

from click.tests.helpers import TestCase
from click.chroot import (
    ClickChroot,
)

class FakeClickChroot(ClickChroot):

    def __init__(self, *args, **kwargs):
        self.temp_dir = kwargs.pop("temp_dir")
        super(FakeClickChroot, self).__init__(*args, **kwargs)
        self._exists = False

    def exists(self):
        return self._exists

    def _debootstrap(self, components, mount):
        os.makedirs(os.path.join(mount, "etc", "apt"))
        os.makedirs(os.path.join(mount, "usr", "sbin"))
        os.makedirs(os.path.join(mount, "sbin"))
        with open(os.path.join(mount, "sbin", "initctl"), "w"):
            pass
        self._exists = True

    @property
    def chroot_config(self):
        p = self.temp_dir + super(FakeClickChroot, self).chroot_config
        if not os.path.exists(os.path.dirname(p)):
            os.makedirs(os.path.dirname(p))
        return p


class TestClickChroot(TestCase):
    def set_dpkg_native_architecture(self, arch):
        """Fool dpkg-architecture into selecting a given native arch."""
        self.use_temp_dir()
        dpkg_script_path = os.path.join(self.temp_dir, "dpkg")
        with open(dpkg_script_path, "w") as dpkg_script:
            print(dedent("""\
                #! /bin/sh
                echo %s
                """) % arch, file=dpkg_script)
        os.chmod(dpkg_script_path, 0o755)
        os.environ["PATH"] = "%s:%s" % (self.temp_dir, os.environ["PATH"])

    def test_get_native_arch_amd64_to_amd64(self):
        chroot = ClickChroot("amd64", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("amd64", chroot._get_native_arch("amd64", "amd64"))

    def test_get_native_arch_amd64_to_armhf(self):
        chroot = ClickChroot("armhf", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("amd64", chroot._get_native_arch("amd64", "armhf"))

    def test_get_native_arch_amd64_to_i386(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("i386", chroot._get_native_arch("amd64", "i386"))

    def test_dpkg_architecture_amd64_to_armhf(self):
        self.set_dpkg_native_architecture("amd64")
        chroot = ClickChroot("armhf", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("amd64", chroot.dpkg_architecture["DEB_BUILD_ARCH"])
        self.assertEqual("armhf", chroot.dpkg_architecture["DEB_HOST_ARCH"])

    def test_dpkg_architecture_i386_to_armhf(self):
        self.set_dpkg_native_architecture("i386")
        chroot = ClickChroot("armhf", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("i386", chroot.dpkg_architecture["DEB_BUILD_ARCH"])
        self.assertEqual("armhf", chroot.dpkg_architecture["DEB_HOST_ARCH"])

    def test_dpkg_architecture_amd64_to_i386(self):
        self.set_dpkg_native_architecture("amd64")
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04", series="trusty")
        self.assertEqual("i386", chroot.dpkg_architecture["DEB_BUILD_ARCH"])
        self.assertEqual("i386", chroot.dpkg_architecture["DEB_HOST_ARCH"])

    def test_gen_sources_archive_only(self):
        chroot = ClickChroot("amd64", "ubuntu-sdk-13.10", series="trusty")
        chroot.native_arch = "i386"
        sources = chroot._generate_sources(
            chroot.series, chroot.native_arch, chroot.target_arch,
            "main")
        self.assertEqual([
            'deb [arch=amd64] http://archive.ubuntu.com/ubuntu trusty main',
            'deb [arch=amd64] http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb [arch=amd64] http://archive.ubuntu.com/ubuntu trusty-security main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-security main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-security main',
        ], sources)

    def test_gen_sources_mixed_archive_ports(self):
        chroot = ClickChroot("armhf", "ubuntu-sdk-13.10", series="trusty")
        chroot.native_arch = "i386"
        sources = chroot._generate_sources(
            chroot.series, chroot.native_arch, chroot.target_arch,
            "main")
        self.assertEqual([
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty main',
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty-updates main',
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty-security main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-security main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-security main',
        ], sources)

    def test_gen_sources_ports_only(self):
        chroot = ClickChroot("armhf", "ubuntu-sdk-13.10", series="trusty")
        chroot.native_arch = "armel"
        sources = chroot._generate_sources(
            chroot.series, chroot.native_arch, chroot.target_arch,
            "main")
        self.assertEqual([
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty main',
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty-updates main',
            'deb [arch=armhf] http://ports.ubuntu.com/ubuntu-ports trusty-security main',
            'deb [arch=armel] http://ports.ubuntu.com/ubuntu-ports trusty main',
            'deb [arch=armel] http://ports.ubuntu.com/ubuntu-ports trusty-updates main',
            'deb [arch=armel] http://ports.ubuntu.com/ubuntu-ports trusty-security main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-security main',
        ], sources)

    def test_gen_sources_native(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04", series="trusty")
        chroot.native_arch = "i386"
        sources = chroot._generate_sources(
            chroot.series, chroot.native_arch, chroot.target_arch,
            "main")
        self.assertEqual([
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb [arch=i386] http://archive.ubuntu.com/ubuntu trusty-security main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-updates main',
            'deb-src http://archive.ubuntu.com/ubuntu trusty-security main',
        ], sources)

    def test_make_cross_package_native(self):
        chroot = ClickChroot("amd64", "ubuntu-sdk-14.04", series="trusty")
        chroot.native_arch = "amd64"
        self.assertEqual("g++", chroot._make_cross_package("g++"))

    def test_make_cross_package_cross(self):
        chroot = ClickChroot("armhf", "ubuntu-sdk-14.04", series="trusty")
        chroot.native_arch = "amd64"
        self.assertEqual(
            "g++-arm-linux-gnueabihf", chroot._make_cross_package("g++"))

    def test_framework_base_base(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04-papi")
        self.assertEqual(chroot.framework_base, "ubuntu-sdk-14.04")

    def test_framework_base_series(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04")
        self.assertEqual(chroot.framework_base, "ubuntu-sdk-14.04")

    def test_chroot_series(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04")
        self.assertEqual(chroot.series, "trusty")

    def test_chroot_full_name(self):
        chroot = ClickChroot("i386", "ubuntu-sdk-14.04")
        self.assertEqual(chroot.full_name, "click-ubuntu-sdk-14.04-i386")

    def test_chroot_create_mocked(self):
        self.use_temp_dir()
        os.environ["http_proxy"] = "http://proxy.example.com/"
        target = "ubuntu-sdk-14.04"
        chroot = FakeClickChroot(
            "i386", target, chroots_dir=self.temp_dir, temp_dir=self.temp_dir)
        with patch.object(chroot, "maint") as mock_maint:
            mock_maint.return_value = 0
            chroot.create()
            mock_maint.assert_called_with("/finish.sh")
            # ensure the following files where created inside the chroot
            for in_chroot in ["etc/localtime",
                              "etc/timezone",
                              "etc/apt/sources.list",
                              "usr/sbin/policy-rc.d"]:
                full_path = os.path.join(
                    self.temp_dir, chroot.full_name, in_chroot)
                self.assertTrue(os.path.exists(full_path))
            # ensure the schroot/chroot.d file was created and looks valid
            schroot_d = os.path.join(
                self.temp_dir, "etc", "schroot", "chroot.d", chroot.full_name)
            self.assertTrue(os.path.exists(schroot_d))

