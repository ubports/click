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


from click.tests.helpers import TestCase
from click.chroot import (
    ClickChroot,
)


class TestClickChroot(TestCase):
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
