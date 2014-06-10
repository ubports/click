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
    "ClickChrootAlreadyExistsException",
    "ClickChrootDoesNotExistException",
    ]


import os
import pwd
import re
import shutil
import stat
import subprocess
import sys


framework_base = {
    "ubuntu-sdk-13.10": "ubuntu-sdk-13.10",
    "ubuntu-sdk-14.04-html-dev1": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-papi-dev1": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-qml-dev1": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-html": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-papi": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-qml": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.10-html-dev1": "ubuntu-sdk-14.10",
    "ubuntu-sdk-14.10-papi-dev1": "ubuntu-sdk-14.10",
    "ubuntu-sdk-14.10-qml-dev1": "ubuntu-sdk-14.10",
    }


framework_series = {
    "ubuntu-sdk-13.10": "saucy",
    "ubuntu-sdk-14.04": "trusty",
    "ubuntu-sdk-14.10": "utopic",
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
    "ubuntu-sdk-14.04": [
        "cmake",
        "libqt5svg5-dev:TARGET",
        "libqt5webkit5-dev:TARGET",
        "libqt5xmlpatterns5-dev:TARGET",
        "libunity-scopes-dev:TARGET",
        "qt3d5-dev:TARGET",
        "qt5-default:TARGET",
        "qtbase5-dev:TARGET",
        "qtdeclarative5-dev:TARGET",
        "qtdeclarative5-dev-tools",
        "qtlocation5-dev:TARGET",
        "qtmultimedia5-dev:TARGET",
        "qtscript5-dev:TARGET",
        "qtsensors5-dev:TARGET",
        "qttools5-dev:TARGET",
        "qttools5-dev-tools:TARGET",
        ],
    "ubuntu-sdk-14.10": [
        "cmake",
        "libqt5svg5-dev:TARGET",
        "libqt5webkit5-dev:TARGET",
        "libqt5xmlpatterns5-dev:TARGET",
        "libunity-scopes-dev:TARGET",
        "qt3d5-dev:TARGET",
        "qt5-default:TARGET",
        "qtbase5-dev:TARGET",
        "qtdeclarative5-dev:TARGET",
        "qtdeclarative5-dev-tools",
        "qtlocation5-dev:TARGET",
        "qtmultimedia5-dev:TARGET",
        "qtscript5-dev:TARGET",
        "qtsensors5-dev:TARGET",
        "qttools5-dev:TARGET",
        "qttools5-dev-tools:TARGET",
        ],
    }


primary_arches = ["amd64", "i386"]


non_meta_re = re.compile(r'^[a-zA-Z0-9+,./:=@_-]+$')


def shell_escape(command):
    escaped = []
    for arg in command:
        if non_meta_re.match(arg):
            escaped.append(arg)
        else:
            escaped.append("'%s'" % arg.replace("'", "'\\''"))
    return " ".join(escaped)


class ClickChrootException(Exception):
    """A generic issue with the chroot"""
    pass


class ClickChrootAlreadyExistsException(ClickChrootException):
    """The chroot already exists"""
    pass


class ClickChrootDoesNotExistException(ClickChrootException):
    """A chroot with that name does not exist yet"""
    pass


class ClickChroot:
    def __init__(self, target_arch, framework, name=None, series=None, session=None):
        self.target_arch = target_arch
        self.framework = framework
        if name is None:
            name = "click"
        self.name = name
        if series is None:
            series = framework_series[self.framework_base]
        self.series = series
        self.session = session
        system_arch = subprocess.check_output(
            ["dpkg", "--print-architecture"],
            universal_newlines=True).strip()
        self.native_arch = self._get_native_arch(system_arch, self.target_arch)
        self.chroots_dir = "/var/lib/schroot/chroots"
        # this doesn't work because we are running this under sudo
        if 'DEBOOTSTRAP_MIRROR' in os.environ:
            self.archive = os.environ['DEBOOTSTRAP_MIRROR']
        else:
            self.archive = "http://archive.ubuntu.com/ubuntu"
        if "SUDO_USER" in os.environ:
            self.user = os.environ["SUDO_USER"]
        elif "PKEXEC_UID" in os.environ:
            self.user = pwd.getpwuid(int(os.environ["PKEXEC_UID"])).pw_name
        else:
            self.user = pwd.getpwuid(os.getuid()).pw_name
        self.dpkg_architecture = self._dpkg_architecture()

    def _get_native_arch(self, system_arch, target_arch):
        """Determine the proper native architecture for a chroot.

        Some combinations of system and target architecture do not require
        cross-building, so in these cases we just create a chroot suitable
        for native building.
        """
        if (system_arch, target_arch) in (
                ("amd64", "i386"),
                # This will only work if the system is running a 64-bit
                # kernel; but there's no alternative since no i386-to-amd64
                # cross-compiler is available in the Ubuntu archive.
                ("i386", "amd64"),
                ):
            return target_arch
        else:
            return system_arch

    def _dpkg_architecture(self):
        dpkg_architecture = {}
        command = ["dpkg-architecture", "-a%s" % self.target_arch]
        env = dict(os.environ)
        env["CC"] = "true"
        # Force dpkg-architecture to recalculate everything rather than
        # picking up values from the environment, which will be present when
        # running the test suite under dpkg-buildpackage.
        for key in list(env):
            if key.startswith("DEB_BUILD_") or key.startswith("DEB_HOST_"):
                del env[key]
        lines = subprocess.check_output(
            command, env=env, universal_newlines=True).splitlines()
        for line in lines:
            try:
                key, value = line.split("=", 1)
            except ValueError:
                continue
            dpkg_architecture[key] = value
        if self.native_arch == self.target_arch:
            # We may have overridden the native architecture (see
            # _get_native_arch above), so we need to force DEB_BUILD_* to
            # match.
            for key in list(dpkg_architecture):
                if key.startswith("DEB_HOST_"):
                    new_key = "DEB_BUILD_" + key[len("DEB_HOST_"):]
                    dpkg_architecture[new_key] = dpkg_architecture[key]
        return dpkg_architecture

    def _generate_sources(self, series, native_arch, target_arch, components):
        ports_mirror = "http://ports.ubuntu.com/ubuntu-ports"
        pockets = ['%s' % series]
        for pocket in ['updates', 'security']:
            pockets.append('%s-%s' % (series, pocket))
        sources = []
        # write binary lines
        arches = [target_arch]
        if native_arch != target_arch:
            arches.append(native_arch)
        for arch in arches:
            if arch not in primary_arches:
                mirror = ports_mirror
            else:
                mirror = self.archive
            for pocket in pockets:
                sources.append("deb [arch=%s] %s %s %s" %
                               (arch, mirror, pocket, components))
        # write source lines
        for pocket in pockets:
            sources.append("deb-src %s %s %s" %
                           (self.archive, pocket, components))

        return sources

    @property
    def framework_base(self):
        if self.framework in framework_base:
            return framework_base[self.framework]
        else:
            return self.framework

    @property
    def full_name(self):
        return "%s-%s-%s" % (self.name, self.framework_base, self.target_arch)

    @property
    def full_session_name(self):
        return "%s-%s" % (self.full_name, self.session)

    def exists(self):
        command = ["schroot", "-c", self.full_name, "-i"]
        with open("/dev/null", "w") as devnull:
            return subprocess.call(
                command, stdout=devnull, stderr=devnull) == 0

    def _make_executable(self, path):
        mode = stat.S_IMODE(os.stat(path).st_mode)
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _make_cross_package(self, prefix):
        if self.native_arch == self.target_arch:
            return prefix
        else:
            target_tuple = self.dpkg_architecture["DEB_HOST_GNU_TYPE"]
            return "%s-%s" % (prefix, target_tuple)

    def create(self, keep_broken_chroot_on_fail=False):
        if self.exists():
            raise ClickChrootAlreadyExistsException(
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
        build_pkgs = [
            "build-essential", "fakeroot",
            "apt-utils", self._make_cross_package("g++"),
            self._make_cross_package("pkg-config"), "cmake",
            "dpkg-cross", "libc-dev:%s" % self.target_arch
            ]
        for package in extra_packages.get(self.framework_base, []):
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
        self._make_executable(daemon_policy)
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
            print("apt-get -y --force-yes dist-upgrade", file=finish)
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
        self._make_executable(finish_script)
        command = ["/finish.sh"]
        ret_code = self.maint(*command)
        if ret_code != 0 and not keep_broken_chroot_on_fail:
            # cleanup on failure
            self.destroy()
            raise ClickChrootException(
                "Failed to create chroot '{}' (exit status {})".format(
                    self.full_name, ret_code))
        return ret_code

    def run(self, *args):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        command = ["schroot", "-c"]
        if self.session:
            command.extend([self.full_session_name, "--run-session"])
        else:
            command.append(self.full_name)
        command.extend(["--", "env"])
        for key, value in self.dpkg_architecture.items():
            command.append("%s=%s" % (key, value))
        command.extend(args)
        ret = subprocess.call(command)
        if ret == 0:
            return 0
        else:
            print("Command returned %d: %s" % (ret, shell_escape(command)),
                  file=sys.stderr)
            return ret

    def maint(self, *args):
        command = [ "schroot", "-u", "root", "-c" ]
        if self.session:
            command.extend([self.full_session_name, "--run-session"])
        else:
            command.append("source:%s" % self.full_name)
        command.append("--")
        command.extend(args)
        ret = subprocess.call(command)
        if ret == 0:
            return 0
        else:
            print("Command returned %d: %s" % (ret, shell_escape(command)),
                  file=sys.stderr)
            return ret

    def install(self, *pkgs):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        ret = self.update()
        if ret != 0:
            return ret
        command = ["apt-get", "install", "--yes"]
        command.extend(pkgs)
        ret = self.maint(*command)
        if ret != 0:
            return ret
        return self.clean()

    def clean(self):
        command = ["apt-get", "clean"]
        return self.maint(*command)

    def update(self):
        command = ["apt-get", "update", "--yes"]
        return self.maint(*command)

    def upgrade(self):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        ret = self.update()
        if ret != 0:
            return ret
        command = ["apt-get", "dist-upgrade", "--yes"]
        ret = self.maint(*command)
        if ret != 0:
            return ret
        return self.clean()

    def destroy(self):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        chroot_config = "/etc/schroot/chroot.d/%s" % self.full_name
        os.remove(chroot_config)
        mount = "%s/%s" % (self.chroots_dir, self.full_name)
        shutil.rmtree(mount)
        return 0

    def begin_session(self):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        command = ["schroot", "-c", self.full_name, "--begin-session",
                   "--session-name", self.full_session_name]
        subprocess.check_call(command)
        return 0

    def end_session(self):
        if not self.exists():
            raise ClickChrootDoesNotExistException(
                "Chroot %s does not exist" % self.full_name)
        command = ["schroot", "-c", self.full_session_name, "--end-session"]
        subprocess.check_call(command)
        return 0
