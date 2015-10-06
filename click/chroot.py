# Copyright (C) 2013 Canonical Ltd.
# Authors: Colin Watson <cjwatson@ubuntu.com>,
#          Brian Murray <brian@ubuntu.com>
#          Michael Vogt <mvo@ubuntu.com>
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

import urllib
import urllib.request
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
from textwrap import dedent
from xml.etree import ElementTree


framework_base = {
    "ubuntu-sdk-13.10": "ubuntu-sdk-13.10",
    # 14.04
    "ubuntu-sdk-14.04-html": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-papi": "ubuntu-sdk-14.04",
    "ubuntu-sdk-14.04-qml": "ubuntu-sdk-14.04",
    # 14.10
    "ubuntu-sdk-14.10-html": "ubuntu-sdk-14.10",
    "ubuntu-sdk-14.10-papi": "ubuntu-sdk-14.10",
    "ubuntu-sdk-14.10-qml": "ubuntu-sdk-14.10",
    # 15.04
    "ubuntu-sdk-15.04-html": "ubuntu-sdk-15.04",
    "ubuntu-sdk-15.04-papi": "ubuntu-sdk-15.04",
    "ubuntu-sdk-15.04-qml": "ubuntu-sdk-15.04",
    # 15.10
    "ubuntu-sdk-15.10-html-dev1": "ubuntu-sdk-15.10-dev1",
    "ubuntu-sdk-15.10-papi-dev1": "ubuntu-sdk-15.10-dev1",
    "ubuntu-sdk-15.10-qml-dev1": "ubuntu-sdk-15.10-dev1",
    }


framework_series = {
    "ubuntu-sdk-13.10": "saucy",
    "ubuntu-sdk-14.04": "trusty",
    "ubuntu-sdk-14.10": "utopic",
    "ubuntu-sdk-15.04": "vivid",
    "ubuntu-sdk-15.10": "wily",
    }


# Please keep the lists of package names sorted.
extra_packages = {
    "ubuntu-sdk-13.10": [
        "libqt5opengl5-dev:{TARGET}",
        "libqt5svg5-dev:{TARGET}",
        "libqt5v8-5-dev:{TARGET}",
        "libqt5webkit5-dev:{TARGET}",
        "libqt5xmlpatterns5-dev:{TARGET}",
        "qmlscene:{TARGET}",
        "qt3d5-dev:{TARGET}",
        "qt5-default:{TARGET}",
        "qt5-qmake:{TARGET}",
        "qtbase5-dev:{TARGET}",
        "qtdeclarative5-dev:{TARGET}",
        "qtmultimedia5-dev:{TARGET}",
        "qtquick1-5-dev:{TARGET}",
        "qtscript5-dev:{TARGET}",
        "qtsensors5-dev:{TARGET}",
        "qttools5-dev:{TARGET}",
        "ubuntu-ui-toolkit-doc",
        ],
    "ubuntu-sdk-14.04": [
        "cmake",
        "google-mock:{TARGET}",
        "intltool",
        "libboost1.54-dev:{TARGET}",
        "libjsoncpp-dev:{TARGET}",
        "libprocess-cpp-dev:{TARGET}",
        "libproperties-cpp-dev:{TARGET}",
        "libqt5svg5-dev:{TARGET}",
        "libqt5webkit5-dev:{TARGET}",
        "libqt5xmlpatterns5-dev:{TARGET}",
        "libunity-scopes-dev:{TARGET}",
        # bug #1316930, needed for autopilot
        "python3",
        "qmlscene:{TARGET}",
        "qt3d5-dev:{TARGET}",
        "qt5-default:{TARGET}",
        "qtbase5-dev:{TARGET}",
        "qtdeclarative5-dev:{TARGET}",
        "qtdeclarative5-dev-tools",
        "qtlocation5-dev:{TARGET}",
        "qtmultimedia5-dev:{TARGET}",
        "qtscript5-dev:{TARGET}",
        "qtsensors5-dev:{TARGET}",
        "qttools5-dev:{TARGET}",
        "qttools5-dev-tools:{TARGET}",
        "ubuntu-ui-toolkit-doc",
        ],
    "ubuntu-sdk-14.10": [
        "cmake",
        "cmake-extras",
        "google-mock:{TARGET}",
        "intltool",
        "libboost1.55-dev:{TARGET}",
        "libcontent-hub-dev:{TARGET}",
        "libjsoncpp-dev:{TARGET}",
        "libnet-cpp-dev:{TARGET}",
        "libprocess-cpp-dev:{TARGET}",
        "libproperties-cpp-dev:{TARGET}",
        "libqt5keychain0:{TARGET}",
        "libqt5sensors5-dev:{TARGET}",
        "libqt5svg5-dev:{TARGET}",
        "libqt5webkit5-dev:{TARGET}",
        "libqt5xmlpatterns5-dev:{TARGET}",
        "libunity-scopes-dev:{TARGET}",
        # bug #1316930, needed for autopilot
        "python3",
        "qml-module-qt-labs-settings:{TARGET}",
        "qml-module-qtmultimedia:{TARGET}",
        "qml-module-qtquick-layouts:{TARGET}",
        "qml-module-qtsensors:{TARGET}",
        "qml-module-qtwebkit:{TARGET}",
        "qmlscene:{TARGET}",
        "qt3d5-dev:{TARGET}",
        "qt5-default:{TARGET}",
        "qtdeclarative5-accounts-plugin:{TARGET}",
        "qtdeclarative5-dev-tools",
        "qtdeclarative5-folderlistmodel-plugin:{TARGET}",
        "qtdeclarative5-localstorage-plugin:{TARGET}",
        "qtdeclarative5-online-accounts-client0.1:{TARGET}",
        "qtdeclarative5-particles-plugin:{TARGET}",
        "qtdeclarative5-poppler1.0:{TARGET}",
        "qtdeclarative5-qtlocation-plugin:{TARGET}",
        "qtdeclarative5-qtorganizer-plugin:{TARGET}",
        "qtdeclarative5-qtpositioning-plugin:{TARGET}",
        "qtdeclarative5-u1db1.0:{TARGET}",
        "qtdeclarative5-ubuntu-content0.1:{TARGET}",
        "qtdeclarative5-ubuntu-download-manager0.1:{TARGET}",
        "qtdeclarative5-ubuntu-mediascanner0.1:{TARGET}",
        "qtdeclarative5-ubuntu-syncmonitor0.1:{TARGET}",
        "qtdeclarative5-ubuntu-telephony-phonenumber0.1:{TARGET}",
        "qtdeclarative5-ubuntu-ui-toolkit-plugin:{TARGET}",
        "qtdeclarative5-usermetrics0.1:{TARGET}",
        "qtdeclarative5-xmllistmodel-plugin:{TARGET}",
        "qtlocation5-dev:{TARGET}",
        "qtmultimedia5-dev:{TARGET}",
        "qtscript5-dev:{TARGET}",
        "qttools5-dev:{TARGET}",
        "qttools5-dev-tools:{TARGET}",
        "ubuntu-html5-theme:{TARGET}",
        "ubuntu-ui-toolkit-doc",
        ],
    "ubuntu-sdk-15.04": [
        # the sdk libs
        "ubuntu-sdk-libs:{TARGET}",
        "ubuntu-sdk-libs-dev:{TARGET}",
        # the native build tools
        "ubuntu-sdk-libs-tools",
        # FIXME: see
        #  http://pad.lv/~mvo/oxide/crossbuild-friendly/+merge/234093
        # we help the apt resolver here until the
        #  oxideqt-codecs/oxidec-codecs-extras is sorted
        "oxideqt-codecs-extra",
        ],
    "ubuntu-sdk-15.10-dev1": [
        # the sdk libs
        "ubuntu-sdk-libs:{TARGET}",
        "ubuntu-sdk-libs-dev:{TARGET}",
        # the native build tools
        "ubuntu-sdk-libs-tools",
        # FIXME: see
        #  http://pad.lv/~mvo/oxide/crossbuild-friendly/+merge/234093
        # we help the apt resolver here until the
        #  oxideqt-codecs/oxidec-codecs-extras is sorted
        "oxideqt-codecs-extra",
        ],
    }


primary_arches = ["amd64", "i386"]


non_meta_re = re.compile(r'^[a-zA-Z0-9+,./:=@_-]+$')


GEOIP_SERVER = "http://geoip.ubuntu.com/lookup"

overlay_ppa = "ci-train-ppa-service/stable-phone-overlay"


def get_geoip_country_code_prefix():
    click_no_local_mirror = os.environ.get('CLICK_NO_LOCAL_MIRROR', 'auto')
    if click_no_local_mirror == '1':
        return ""
    try:
        with urllib.request.urlopen(GEOIP_SERVER) as f:
            xml_data = f.read()
        et = ElementTree.fromstring(xml_data)
        cc = et.find("CountryCode")
        if not cc:
            return ""
        return cc.text.lower()+"."
    except (ElementTree.ParseError, urllib.error.URLError):
        pass
    return ""


def generate_sources(series, native_arch, target_arch,
                     archive_mirror, ports_mirror, components):
    """Generate a list of strings for apts sources.list.
    Arguments:
    series -- the distro series (e.g. vivid)
    native_arch -- the native architecture (e.g. amd64)
    target_arch -- the target architecture (e.g. armhf)
    archive_mirror -- main mirror, e.g. http://archive.ubuntu.com/ubuntu
    ports_mirror -- ports mirror, e.g. http://ports.ubuntu.com/ubuntu-ports
    components -- the components as string, e.g. "main restricted universe"
    """
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
            mirror = archive_mirror
        for pocket in pockets:
            sources.append("deb [arch=%s] %s %s %s" %
                           (arch, mirror, pocket, components))
    # write source lines
    for pocket in pockets:
        sources.append("deb-src %s %s %s" %
                       (archive_mirror, pocket, components))
    return sources


def shell_escape(command):
    escaped = []
    for arg in command:
        if non_meta_re.match(arg):
            escaped.append(arg)
        else:
            escaped.append("'%s'" % arg.replace("'", "'\\''"))
    return " ".join(escaped)


def strip_dev_series_from_framework(framework):
    """Remove trailing -dev[0-9]+ from a framework name"""
    return re.sub(r'^(.*)-dev[0-9]+$', r'\1', framework)


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

    DAEMON_POLICY = dedent("""\
    #!/bin/sh
    while true; do
        case "$1" in
          -*) shift ;;
          makedev) exit 0;;
          x11-common) exit 0;;
          *) exit 101;;
        esac
    done
    """)

    def __init__(self, target_arch, framework, name=None, series=None,
                 session=None, chroots_dir=None):
        self.target_arch = target_arch
        self.framework = strip_dev_series_from_framework(framework)
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
        if chroots_dir is None:
            chroots_dir = "/var/lib/schroot/chroots"
        self.chroots_dir = chroots_dir

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

    def _generate_chroot_config(self, mount):
        admin_user = "root"
        users = []
        for key in ("users", "root-users", "source-root-users"):
            users.append("%s=%s,%s" % (key, admin_user, self.user))
        with open(self.chroot_config, "w") as target:
            target.write(dedent("""\
            [{full_name}]
            description=Build chroot for click packages on {target_arch}
            {users}
            type=directory
            profile=default
            setup.fstab=click/fstab
            # Not protocols or services see
            # debian bug 557730
            setup.nssdatabases=sbuild/nssdatabases
            union-type=overlayfs
            directory={mount}
            """).format(full_name=self.full_name,
                        target_arch=self.target_arch,
                        users="\n".join(users),
                        mount=mount))

    def _generate_daemon_policy(self, mount):
        daemon_policy = "%s/usr/sbin/policy-rc.d" % mount
        with open(daemon_policy, "w") as policy:
            policy.write(self.DAEMON_POLICY)
        return daemon_policy

    def _generate_apt_proxy_file(self, mount, proxy):
        apt_conf_d = os.path.join(mount, "etc", "apt", "apt.conf.d")
        if not os.path.exists(apt_conf_d):
            os.makedirs(apt_conf_d)
        apt_conf_f = os.path.join(apt_conf_d, "99-click-chroot-proxy")
        if proxy:
            with open(apt_conf_f, "w") as f:
                f.write(dedent("""\
                // proxy settings copied by click chroot
                Acquire {
                    HTTP {
                        Proxy "%s";
                    };
                };
                """) % proxy)
        return apt_conf_f

    def _generate_finish_script(self, mount, build_pkgs):
        finish_script = "%s/finish.sh" % mount
        with open(finish_script, 'w') as finish:
            finish.write(dedent("""\
                #!/bin/bash
                set -e
                # Configure target arch
                dpkg --add-architecture {target_arch}
                # Reload package lists
                apt-get update || true
                # Pull down signature requirements
                apt-get -y --force-yes install gnupg ubuntu-keyring
            """).format(target_arch=self.target_arch))
            if self.series == "vivid":
                finish.write(dedent("""\
                    apt-get -y --force-yes install software-properties-common
                    add-apt-repository -y ppa:{ppa}
                    echo "Package: *"  \
                        > /etc/apt/preferences.d/stable-phone-overlay.pref
                    echo \
                        "Pin: release o=LP-PPA-{pin_ppa}" \
                        >> /etc/apt/preferences.d/stable-phone-overlay.pref
                    echo "Pin-Priority: 1001" \
                        >> /etc/apt/preferences.d/stable-phone-overlay.pref
                """).format(ppa=overlay_ppa,
                            pin_ppa=re.sub('/', '-', overlay_ppa)))
            finish.write(dedent("""\
                # Reload package lists
                apt-get update || true
                # Disable debconf questions
                # so that automated builds won't prompt
                echo set debconf/frontend Noninteractive | debconf-communicate
                echo set debconf/priority critical | debconf-communicate
                apt-get -y --force-yes dist-upgrade
                # Install basic build tool set to match buildd
                apt-get -y --force-yes install {build_pkgs}
                # Set up expected /dev entries
                if [ ! -r /dev/stdin ];  then
                    ln -s /proc/self/fd/0 /dev/stdin
                fi
                if [ ! -r /dev/stdout ]; then
                    ln -s /proc/self/fd/1 /dev/stdout
                fi
                if [ ! -r /dev/stderr ]; then
                    ln -s /proc/self/fd/2 /dev/stderr
                fi
                # Clean up
                rm /finish.sh
                apt-get clean
            """).format(build_pkgs=' '.join(build_pkgs)))
        return finish_script

    def _debootstrap(self, components, mount, archive):
        subprocess.check_call([
            "debootstrap",
            "--arch", self.native_arch,
            "--variant=buildd",
            "--components=%s" % ','.join(components),
            self.series,
            mount,
            archive
            ])

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

    @property
    def chroot_config(self):
        return "/etc/schroot/chroot.d/%s" % self.full_name

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
                'unset x; eval "$(apt-config shell x Acquire::HTTP::Proxy)"; \
                 echo "$x"',
                shell=True, universal_newlines=True).strip()
        build_pkgs = [
            # sort alphabetically
            "apt-utils",
            "build-essential",
            "cmake",
            "dpkg-cross",
            "fakeroot",
            "libc-dev:%s" % self.target_arch,
            # build pkg names dynamically
            self._make_cross_package("g++"),
            self._make_cross_package("pkg-config"),
        ]
        for package in extra_packages.get(self.framework_base, []):
            package = package.format(TARGET=self.target_arch)
            build_pkgs.append(package)
        os.makedirs(mount)

        country_code = get_geoip_country_code_prefix()
        archive = "http://%sarchive.ubuntu.com/ubuntu" % country_code
        ports_mirror = "http://%sports.ubuntu.com/ubuntu-ports" % country_code
        # this doesn't work because we are running this under sudo
        if 'DEBOOTSTRAP_MIRROR' in os.environ:
            archive = os.environ['DEBOOTSTRAP_MIRROR']
        self._debootstrap(components, mount, archive)
        sources = generate_sources(self.series, self.native_arch,
                                   self.target_arch,
                                   archive, ports_mirror,
                                   ' '.join(components))
        with open("%s/etc/apt/sources.list" % mount, "w") as sources_list:
            for line in sources:
                print(line, file=sources_list)
        shutil.copy2("/etc/localtime", "%s/etc/" % mount)
        shutil.copy2("/etc/timezone", "%s/etc/" % mount)
        self._generate_chroot_config(mount)
        daemon_policy = self._generate_daemon_policy(mount)
        self._make_executable(daemon_policy)
        initctl = "%s/sbin/initctl" % mount
        if os.path.exists(initctl):
            os.remove(initctl)
            os.symlink("%s/bin/true" % mount, initctl)
        self._generate_apt_proxy_file(mount, proxy)
        finish_script = self._generate_finish_script(mount, build_pkgs)
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
        command = ["schroot", "-u", "root", "-c"]
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
        # remove config
        if os.path.exists(self.chroot_config):
            os.remove(self.chroot_config)
        # find all schroot mount points, this is actually quite complicated
        mount_dir = os.path.abspath(
            os.path.join(self.chroots_dir, "..", "mount"))
        needle = os.path.join(mount_dir, self.full_name)
        all_mounts = []
        with open("/proc/mounts") as f:
            for line in f.readlines():
                mp = line.split()[1]
                if mp.startswith(needle):
                    all_mounts.append(mp)
        # reverse order is important in case of submounts
        for mp in sorted(all_mounts, key=len, reverse=True):
            subprocess.call(["umount", mp])
        # now remove the rest
        chroot_dir = "%s/%s" % (self.chroots_dir, self.full_name)
        if os.path.exists(chroot_dir):
            shutil.rmtree(chroot_dir)
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
