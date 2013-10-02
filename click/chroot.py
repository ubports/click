# Copyright (C) 2013 Canonical Ltd.
# Authors: Colin Watson <cjwatson@ubuntu.com>,
#          Brian Murray <brian@ubuntu.com>
#
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

"""Chroot management for building Click packages."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "ClickChroot",
    "ClickChrootException",
    ]


import os
import shutil
import stat
import subprocess


extra_packages = {
    "ubuntu-sdk-13.10": [
        "libqt5opengl5-dev:TARGET",
        "libqt5webkit5-dev:TARGET",
        "libqt5xmlpatterns5-dev:TARGET",
        "qt5-default:TARGET",
        "qt5-qmake:TARGET",
        "qtbase5-dev:TARGET",
        "qtdeclarative5-dev:TARGET",
        "qtquick1-5-dev:TARGET",
        "qtscript5-dev:TARGET",
        "qtsensors5-dev:TARGET",
        ],
    }


class ClickChrootException(Exception):
    pass


class ClickChroot:
    def __init__(self, series, target_arch, framework, name=None):
        if name is None:
            name = "click"
        self.series = series
        self.target_arch = target_arch
        self.framework = framework
        self.name = name
        self.native_arch = subprocess.check_output(
            ["dpkg", "--print-architecture"]).decode('utf-8').strip()
        self.chroots_dir = "/var/lib/schroot/chroots"
        # this doesn't work because we are running this under sudo
        if 'DEBOOTSTRAP_MIRROR' in os.environ:
            self.archive = os.environ['DEBOOTSTRAP_MIRROR']
        else:
            self.archive = "http://archive.ubuntu.com"

    def _generate_sources(self, series, native_arch, target_arch, components):
        ports_mirror = "http://ports.ubuntu.com/ubuntu-ports"
        pockets = ['%s' % series]
        for pocket in ['updates', 'security']:
            pockets.append('%s-%s' % (series, pocket))
        sources = []
        if target_arch in ['armhf']:
            for pocket in pockets:
                sources.append("deb [arch=%s] %s %s %s" %
                               (target_arch, ports_mirror, pocket, components))
                sources.append("deb-src %s %s %s" %
                               (ports_mirror, pocket, components))
        if native_arch in ['i386', 'amd64']:
            for pocket in pockets:
                sources.append("deb [arch=%s] %s %s %s" %
                               (native_arch, self.archive, pocket, components))
                sources.append("deb-src %s %s %s" %
                               (self.archive, pocket, components))
        return sources

    @property
    def full_name(self):
        return "%s-%s-%s-%s-%s" % (
            self.name, self.framework, self.series, self.native_arch,
            self.target_arch)

    def exists(self):
        command = ["schroot", "-c", self.full_name, "-i"]
        with open("/dev/null", "w") as devnull:
            return subprocess.call(
                command, stdout=devnull, stderr=devnull) == 0

    def create(self):
        if self.exists():
            raise ClickChrootException(
                "Chroot %s already exists" % self.full_name)
        components = ["main", "restricted", "universe", "multiverse"]
        mount = "%s/%s" % (self.chroots_dir, self.full_name)
        proxy = None
        if not proxy and "http_proxy" in os.environ:
            proxy = os.environ["http_proxy"]
        if not proxy:
            proxy = subprocess.check_output(
                ["apt-config", "shell", "x", "Acquire::HTTP::Proxy"]
                ).decode('utf-8').replace('x=', '').strip()
        with open("/dev/null", "w") as devnull:
            target_tuple = subprocess.check_output(
                ["dpkg-architecture", "-a%s" % self.target_arch,
                 "-qDEB_HOST_GNU_TYPE"], stderr=devnull
                ).decode('utf-8').strip()
        build_pkgs = [
            "build-essential", "fakeroot",
            "apt-utils", "pkg-create-dbgsym",
            "pkgbinarymangler", "g++-%s" % target_tuple,
            "pkg-config-%s" % target_tuple,
            "dpkg-cross", "libc-dev:%s" % self.target_arch
            ]
        for package in extra_packages.get(self.framework, []):
            package = package.replace(":TARGET", ":%s" % self.target_arch)
            build_pkgs.append(package)
        os.makedirs(mount)
        subprocess.check_call([
            "debootstrap",
            "--arch", self.native_arch,
            "--variant=buildd",
            "--components=%s" % ','.join(components),
            self.series,
            mount,
            self.archive
            ])
        sources = self._generate_sources(self.series, self.native_arch,
                                         self.target_arch,
                                         ' '.join(components))
        with open("%s/etc/apt/sources.list" % mount, "w") as sources_list:
            for line in sources:
                print(line, file=sources_list)
        shutil.copy("/etc/localtime", "%s/etc/" % mount)
        shutil.copy("/etc/timezone", "%s/etc/" % mount)
        chroot_config = "/etc/schroot/chroot.d/%s" % self.full_name
        with open(chroot_config, "w") as target:
            admin_groups = "sbuild,root"
            print("[%s]" % self.full_name, file=target)
            print("description=Build chroot for click packages on %s" %
                  self.target_arch, file=target)
            for group in ["groups", "root-groups", "source-root-users",
                          "source-root-groups"]:
                print("%s=%s" % (group, admin_groups), file=target)
            print("type=directory", file=target)
            print("profile=sbuild", file=target)
            print("union-type=overlayfs", file=target)
            print("directory=%s" % mount, file=target)
        # disable daemons?
        finish_script = "%s/finish.sh" % mount
        with open(finish_script, 'w') as finish:
            print("#!/bin/bash", file=finish)
            print("set -e", file=finish)
            if proxy:
                print("mkdir -p /etc/apt/apt.conf.d", file=finish)
                print("cat > /etc/apt/apt.conf.d/99-click-chroot-proxy <<EOF",
                      file=finish)
                print("// proxy settings copied by click-chroot", file=finish)
                print('Acquire { HTTP { Proxy "%s"; }; };' % proxy,
                      file=finish)
                print("EOF", file=finish)
            print("# Configure target arch", file=finish)
            print("dpkg --add-architecture %s" % self.target_arch,
                  file=finish)
            print("# Reload package lists", file=finish)
            print("apt-get update || true", file=finish)
            print("# Pull down signature requirements", file=finish)
            print("apt-get -y --force-yes install \
gnupg ubuntu-keyring", file=finish)
            print("# Reload package lists", file=finish)
            print("apt-get update || true", file=finish)
            print("# Disable debconf questions so that automated \
builds won't prompt", file=finish)
            print("echo set debconf/frontend Noninteractive | \
debconf-communicate", file=finish)
            print("echo set debconf/priority critical | \
debconf-communicate", file=finish)
            print("# Install basic build tool set to match buildd",
                  file=finish)
            print("apt-get -y --force-yes install %s"
                  % ' '.join(build_pkgs), file=finish)
            print("# Set up expected /dev entries", file=finish)
            print("if [ ! -r /dev/stdin ];  \
then ln -s /proc/self/fd/0 /dev/stdin;  fi", file=finish)
            print("if [ ! -r /dev/stdout ]; \
then ln -s /proc/self/fd/1 /dev/stdout; fi", file=finish)
            print("if [ ! -r /dev/stderr ]; \
then ln -s /proc/self/fd/2 /dev/stderr; fi", file=finish)
            print("# Clean up", file=finish)
            print("rm /finish.sh", file=finish)
            print("apt-get clean", file=finish)
        os.chmod(finish_script, stat.S_IEXEC)
        command = ["/finish.sh"]
        self.maint(*command)

    def run(self, *args):
        if not self.exists():
            raise ClickChrootException(
                "Chroot %s does not exist" % self.full_name)
        command = ["schroot", "-c", self.full_name, "--directory=/", "--"]
        command.extend(args)
        subprocess.check_call(command)

    def maint(self, *args):
        command = [
            # directory is a workaround for the click or user's home directory
            # not existing
            "schroot", "-c", "source:%s" % self.full_name,
            "-u", "root", "--directory=/", "--",
            ]
        command.extend(args)
        subprocess.check_call(command)

    def install(self, *pkgs):
        if not self.exists():
            raise ClickChrootException(
                "Chroot %s does not exist" % self.full_name)
        self.update()
        command = ["apt-get", "install", "--yes"]
        command.extend(pkgs)
        self.maint(*command)
        self.clean()

    def clean(self):
        command = ["apt-get", "clean"]
        self.maint(*command)

    def update(self):
        command = ["apt-get", "update", "--yes"]
        self.maint(*command)

    def upgrade(self):
        if not self.exists():
            raise ClickChrootException(
                "Chroot %s does not exist" % self.full_name)
        self.update()
        command = ["apt-get", "dist-upgrade", "--yes"]
        self.maint(*command)
        self.clean()

    def destroy(self):
        if not self.exists():
            raise ClickChrootException(
                "Chroot %s does not exist" % self.full_name)
        chroot_config = "/etc/schroot/chroot.d/%s" % self.full_name
        os.remove(chroot_config)
        mount = "%s/%s" % (self.chroots_dir, self.full_name)
        shutil.rmtree(mount)
