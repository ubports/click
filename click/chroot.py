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
import pwd
import shutil
import stat
import subprocess


framework_series = {
    "ubuntu-sdk-13.10": "saucy",
    }


# Please keep the lists of package names sorted.
extra_packages = {
    "ubuntu-sdk-13.10": [
        "libqt5opengl5-dev:TARGET",
        "libqt5svg5-dev:TARGET",
        "libqt5v8-5-dev:TARGET",
        "libqt5webkit5-dev:TARGET",
        "libqt5xmlpatterns5-dev:TARGET",
        "qt3d5-dev:TARGET",
        "qt5-default:TARGET",
        "qt5-qmake:TARGET",
        "qtbase5-dev:TARGET",
        "qtdeclarative5-dev:TARGET",
        "qtmultimedia5-dev:TARGET",
        "qtquick1-5-dev:TARGET",
        "qtscript5-dev:TARGET",
        "qtsensors5-dev:TARGET",
        "qttools5-dev:TARGET",
        ],
    }


primary_arches = ["amd64", "i386"]


class ClickChrootException(Exception):
    pass


class ClickChroot:
    def __init__(self, target_arch, framework, name=None, series=None):
        if name is None:
            name = "click"
        if series is None:
            series = framework_series[framework]
        self.target_arch = target_arch
        self.framework = framework
        self.name = name
        self.series = series
        self.native_arch = subprocess.check_output(
            ["dpkg", "--print-architecture"],
            universal_newlines=True).strip()
        self.chroots_dir = "/var/lib/schroot/chroots"
        # this doesn't work because we are running this under sudo
        if 'DEBOOTSTRAP_MIRROR' in os.environ:
            self.archive = os.environ['DEBOOTSTRAP_MIRROR']
        else:
            self.archive = "http://archive.ubuntu.com/ubuntu"
        if "SUDO_USER" in os.environ:
            self.user = os.environ["SUDO_USER"]
        else:
            self.user = pwd.getpwuid(os.getuid()).pw_name
        self.dpkg_architecture = self._dpkg_architecture()

    def _dpkg_architecture(self):
        dpkg_architecture = {}
        command = ["dpkg-architecture", "-a%s" % self.target_arch]
        env = dict(os.environ)
        env["CC"] = "true"
        lines = subprocess.check_output(
            command, env=env, universal_newlines=True).splitlines()
        for line in lines:
            try:
                key, value = line.split("=", 1)
            except ValueError:
                continue
            dpkg_architecture[key] = value
        return dpkg_architecture

    def _generate_sources(self, series, native_arch, target_arch, components):
        ports_mirror = "http://ports.ubuntu.com/ubuntu-ports"
        pockets = ['%s' % series]
        for pocket in ['updates', 'security']:
            pockets.append('%s-%s' % (series, pocket))
        sources = []
        if target_arch not in primary_arches:
            for pocket in pockets:
                sources.append("deb [arch=%s] %s %s %s" %
                               (target_arch, ports_mirror, pocket, components))
                sources.append("deb-src %s %s %s" %
                               (ports_mirror, pocket, components))
        if native_arch in primary_arches:
            for pocket in pockets:
                sources.append("deb [arch=%s] %s %s %s" %
                               (native_arch, self.archive, pocket, components))
                sources.append("deb-src %s %s %s" %
                               (self.archive, pocket, components))
        return sources

    @property
    def full_name(self):
        return "%s-%s-%s" % (self.name, self.framework, self.target_arch)

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
                'unset x; eval "$(apt-config shell x Acquire::HTTP::Proxy)"; echo "$x"',
                shell=True, universal_newlines=True).strip()
        target_tuple = self.dpkg_architecture["DEB_HOST_GNU_TYPE"]
        build_pkgs = [
            "build-essential", "fakeroot",
            "apt-utils", "g++-%s" % target_tuple,
            "pkg-config-%s" % target_tuple, "cmake",
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
        shutil.copy2("/etc/localtime", "%s/etc/" % mount)
        shutil.copy2("/etc/timezone", "%s/etc/" % mount)
        chroot_config = "/etc/schroot/chroot.d/%s" % self.full_name
        with open(chroot_config, "w") as target:
            admin_user = "root"
            print("[%s]" % self.full_name, file=target)
            print("description=Build chroot for click packages on %s" %
                  self.target_arch, file=target)
            for key in ("users", "root-users", "source-root-users"):
                print("%s=%s,%s" % (key, admin_user, self.user), file=target)
            print("type=directory", file=target)
            print("profile=default", file=target)
            print("setup.fstab=click/fstab", file=target)
            print("# Not protocols or services see ", file=target)
            print("# debian bug 557730", file=target)
            print("setup.nssdatabases=sbuild/nssdatabases",
                file=target)
            print("union-type=overlayfs", file=target)
            print("directory=%s" % mount, file=target)
        daemon_policy = "%s/usr/sbin/policy-rc.d" % mount
        with open(daemon_policy, "w") as policy:
            print("#!/bin/sh", file=policy)
            print("while true; do", file=policy)
            print('    case "$1" in', file=policy)
            print("      -*) shift ;;", file=policy)
            print("      makedev) exit 0;;", file=policy)
            print("      x11-common) exit 0;;", file=policy)
            print("      *) exit 101;;", file=policy)
            print("    esac", file=policy)
            print("done", file=policy)
        os.remove("%s/sbin/initctl" % mount)
        os.symlink("%s/bin/true" % mount, "%s/sbin/initctl" % mount)
        finish_script = "%s/finish.sh" % mount
        with open(finish_script, 'w') as finish:
            print("#!/bin/bash", file=finish)
            print("set -e", file=finish)
            if proxy:
                print("mkdir -p /etc/apt/apt.conf.d", file=finish)
                print("cat > /etc/apt/apt.conf.d/99-click-chroot-proxy <<EOF",
                      file=finish)
                print("// proxy settings copied by click chroot", file=finish)
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
        command = ["schroot", "-c", self.full_name, "--", "env"]
        for key, value in self.dpkg_architecture.items():
            command.append("%s=%s" % (key, value))
        command.extend(args)
        subprocess.check_call(command)

    def maint(self, *args):
        command = [
            "schroot", "-c", "source:%s" % self.full_name, "-u", "root", "--",
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
