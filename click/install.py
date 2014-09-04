# Copyright (C) 2013 Canonical Ltd.
# Author: Colin Watson <cjwatson@ubuntu.com>

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

"""Installing Click packages."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'ClickInstaller',
    'ClickInstallerAuditError',
    'ClickInstallerError',
    'ClickInstallerPermissionDenied',
    ]


from functools import partial
import grp
import inspect
import json
import logging
import os
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile

from contextlib import closing

import apt_pkg
from debian.debfile import DebFile as _DebFile
from debian.debian_support import Version
from gi.repository import Click

from click.paths import preload_path
from click.preinst import static_preinst_matches
from click.versions import spec_version

from click.framework import (
    validate_framework,
    ClickFrameworkInvalid,
)


try:
    _DebFile.close
    DebFile = _DebFile
except AttributeError:
    # Yay!  The Ubuntu 13.04 version of python-debian 0.1.21
    # debian.debfile.DebFile has a .close() method but the PyPI version of
    # 0.1.21 does not.  It's worse than that because DebFile.close() really
    # delegates to DebPart.close() and *that's* missing in the PyPI version.
    # To get that working, we have to reach inside the object and name mangle
    # the attribute.
    class DebFile(_DebFile):
        def close(self):
            self.control._DebPart__member.close()
            self.data._DebPart__member.close()


apt_pkg.init_system()


class DebsigVerifyError(Exception):
    pass


class DebsigVerify:
    """Tiny wrapper around the debsig-verify commandline"""
    # from debsig-verify-0.9/debsigs.h
    DS_SUCCESS = 0
    DS_FAIL_NOSIGS = 10
    DS_FAIL_UNKNOWN_ORIGIN = 11
    DS_FAIL_NOPOLICIES = 12
    DS_FAIL_BADSIG = 13
    DS_FAIL_INTERNAL = 14

    # should be a property, but python does not support support
    # class properties easily
    @classmethod
    def available(cls):
        return Click.find_on_path("debsig-verify")

    @classmethod
    def verify(cls, path, allow_unauthenticated):
        command = ["debsig-verify"] + [path]
        try:
            subprocess.check_output(command, universal_newlines=True)
        except subprocess.CalledProcessError as e:
            if (allow_unauthenticated and
                e.returncode in (DebsigVerify.DS_FAIL_NOSIGS,
                                 DebsigVerify.DS_FAIL_UNKNOWN_ORIGIN,
                                 DebsigVerify.DS_FAIL_NOPOLICIES)):
                logging.warning(
                    "Signature check failed, but installing anyway "
                    "as requested")
            else:
                raise DebsigVerifyError(
                    "Signature verification error: %s" % e.output)
        return True


class ClickInstallerError(Exception):
    pass


class ClickInstallerPermissionDenied(ClickInstallerError):
    pass


class ClickInstallerAuditError(ClickInstallerError):
    pass


class ClickInstaller:
    def __init__(self, db, force_missing_framework=False,
                 allow_unauthenticated=False):
        self.db = db
        self.force_missing_framework = force_missing_framework
        self.allow_unauthenticated = allow_unauthenticated

    def _preload_path(self):
        if "CLICK_PACKAGE_PRELOAD" in os.environ:
            return os.environ["CLICK_PACKAGE_PRELOAD"]
        my_path = inspect.getsourcefile(ClickInstaller)
        preload = os.path.join(
            os.path.dirname(my_path), os.pardir, "preload", ".libs",
            "libclickpreload.so")
        if os.path.exists(preload):
            return os.path.abspath(preload)
        return preload_path

    def _dpkg_architecture(self):
        return subprocess.check_output(
            ["dpkg", "--print-architecture"],
            universal_newlines=True).rstrip("\n")

    def extract(self, path, target):
        command = ["dpkg-deb", "-R", path, target]
        with open(path, "rb") as fd:
            env = dict(os.environ)
            preloads = [self._preload_path()]
            if "LD_PRELOAD" in env:
                preloads.append(env["LD_PRELOAD"])
            env["LD_PRELOAD"] = " ".join(preloads)
            env["CLICK_BASE_DIR"] = target
            env["CLICK_PACKAGE_PATH"] = path
            env["CLICK_PACKAGE_FD"] = str(fd.fileno())
            env.pop("HOME", None)
            kwargs = {}
            if sys.version >= "3.2":
                kwargs["pass_fds"] = (fd.fileno(),)
            subprocess.check_call(command, env=env, **kwargs)

    def audit(self, path, slow=False, check_arch=False):
        # always do the signature check first
        if DebsigVerify.available():
            try:
                DebsigVerify.verify(path, self.allow_unauthenticated)
            except DebsigVerifyError as e:
                raise ClickInstallerAuditError(str(e))
        else:
            logging.warning(
                "debsig-verify not available; cannot check signatures")

        with closing(DebFile(filename=path)) as package:
            control_fields = package.control.debcontrol()

            try:
                click_version = Version(control_fields["Click-Version"])
            except KeyError:
                raise ClickInstallerAuditError("No Click-Version field")
            if click_version > spec_version:
                raise ClickInstallerAuditError(
                    "Click-Version: %s newer than maximum supported version "
                    "%s" % (click_version, spec_version))

            for field in (
                "Pre-Depends", "Depends", "Recommends", "Suggests", "Enhances",
                "Conflicts", "Breaks",
                "Provides",
            ):
                if field in control_fields:
                    raise ClickInstallerAuditError(
                        "%s field is forbidden in Click packages" % field)

            scripts = package.control.scripts()
            if ("preinst" in scripts and
                    static_preinst_matches(scripts["preinst"])):
                scripts.pop("preinst", None)
            if scripts:
                raise ClickInstallerAuditError(
                    "Maintainer scripts are forbidden in Click packages "
                    "(found: %s)" %
                    " ".join(sorted(scripts)))

            if not package.control.has_file("manifest"):
                raise ClickInstallerAuditError("Package has no manifest")
            with package.control.get_file("manifest", encoding="UTF-8") as f:
                manifest = json.load(f)

            try:
                package_name = manifest["name"]
            except KeyError:
                raise ClickInstallerAuditError('No "name" entry in manifest')
            # TODO: perhaps just do full name validation?
            if "/" in package_name:
                raise ClickInstallerAuditError(
                    'Invalid character "/" in "name" entry: %s' % package_name)
            if "_" in package_name:
                raise ClickInstallerAuditError(
                    'Invalid character "_" in "name" entry: %s' % package_name)

            try:
                package_version = manifest["version"]
            except KeyError:
                raise ClickInstallerAuditError(
                    'No "version" entry in manifest')
            # TODO: perhaps just do full version validation?
            if "/" in package_version:
                raise ClickInstallerAuditError(
                    'Invalid character "/" in "version" entry: %s' %
                    package_version)
            if "_" in package_version:
                raise ClickInstallerAuditError(
                    'Invalid character "_" in "version" entry: %s' %
                    package_version)

            try:
                framework = manifest["framework"]
            except KeyError:
                raise ClickInstallerAuditError(
                    'No "framework" entry in manifest')
            try:
                validate_framework(framework, self.force_missing_framework)
            except ClickFrameworkInvalid as e:
                raise ClickInstallerAuditError(str(e))

            if check_arch:
                architecture = manifest.get("architecture", "all")
                if architecture != "all":
                    dpkg_architecture = self._dpkg_architecture()
                    if isinstance(architecture, list):
                        if dpkg_architecture not in architecture:
                            raise ClickInstallerAuditError(
                                'Package architectures "%s" not compatible '
                                'with system architecture "%s"' %
                                (" ".join(architecture), dpkg_architecture))
                    elif architecture != dpkg_architecture:
                        raise ClickInstallerAuditError(
                            'Package architecture "%s" not compatible '
                            'with system architecture "%s"' %
                            (architecture, dpkg_architecture))

            if slow:
                temp_dir = tempfile.mkdtemp(prefix="click")
                try:
                    self.extract(path, temp_dir)
                    command = [
                        "md5sum", "-c", "--quiet",
                        os.path.join("DEBIAN", "md5sums"),
                    ]
                    subprocess.check_call(command, cwd=temp_dir)
                finally:
                    shutil.rmtree(temp_dir)

            return package_name, package_version

    def _drop_privileges(self, username):
        if os.geteuid() != 0:
            return
        pw = pwd.getpwnam(username)
        os.setgroups(
            [g.gr_gid for g in grp.getgrall() if username in g.gr_mem])
        # Portability note: this assumes that we have [gs]etres[gu]id, which
        # is true on Linux but not necessarily elsewhere.  If you need to
        # support something else, there are reasonably standard alternatives
        # involving other similar calls; see e.g. gnulib/lib/idpriv-drop.c.
        os.setresgid(pw.pw_gid, pw.pw_gid, pw.pw_gid)
        os.setresuid(pw.pw_uid, pw.pw_uid, pw.pw_uid)
        assert os.getresuid() == (pw.pw_uid, pw.pw_uid, pw.pw_uid)
        assert os.getresgid() == (pw.pw_gid, pw.pw_gid, pw.pw_gid)
        os.umask(0o022)

    def _euid_access(self, username, path, mode):
        """Like os.access, but for the effective UID."""
        # TODO: Dropping privileges and calling
        # os.access(effective_ids=True) ought to work, but for some reason
        # appears not to return False when it should.  It seems that we need
        # a subprocess to check this reliably.  At least we don't have to
        # exec anything.
        pid = os.fork()
        if pid == 0:  # child
            self._drop_privileges(username)
            os._exit(0 if os.access(path, mode) else 1)
        else:  # parent
            _, status = os.waitpid(pid, 0)
            return status == 0

    def _check_write_permissions(self, path):
        while True:
            if os.path.exists(path):
                break
            path = os.path.dirname(path)
            if path == "/":
                break
        if not self._euid_access("clickpkg", path, os.W_OK):
            raise ClickInstallerPermissionDenied(
                'Cannot acquire permission to write to %s; either run as root '
                'with --user, or use "pkcon install-local" instead' % path)

    def _install_preexec(self, inst_dir):
        self._drop_privileges("clickpkg")

        admin_dir = os.path.join(inst_dir, ".click")
        if not os.path.exists(admin_dir):
            os.makedirs(admin_dir)
            with open(os.path.join(admin_dir, "available"), "w"):
                pass
            with open(os.path.join(admin_dir, "status"), "w"):
                pass
            os.mkdir(os.path.join(admin_dir, "info"))
            os.mkdir(os.path.join(admin_dir, "updates"))
            os.mkdir(os.path.join(admin_dir, "triggers"))

    def _unpack(self, path, user=None, all_users=False):
        package_name, package_version = self.audit(path, check_arch=True)

        # Is this package already unpacked in an underlay (non-topmost)
        # database?
        if self.db.has_package_version(package_name, package_version):
            overlay = self.db.get(self.db.props.size - 1)
            if not overlay.has_package_version(package_name, package_version):
                return package_name, package_version, None

        package_dir = os.path.join(self.db.props.overlay, package_name)
        inst_dir = os.path.join(package_dir, package_version)
        assert (
            os.path.dirname(os.path.dirname(inst_dir)) ==
            self.db.props.overlay)

        self._check_write_permissions(self.db.props.overlay)
        root_click = os.path.join(self.db.props.overlay, ".click")
        if not os.path.exists(root_click):
            os.makedirs(root_click)
            if os.geteuid() == 0:
                pw = pwd.getpwnam("clickpkg")
                os.chown(root_click, pw.pw_uid, pw.pw_gid)

        # TODO: sandbox so that this can only write to the unpack directory
        command = [
            "dpkg",
            # We normally run dpkg as non-root.
            "--force-not-root",
            # /sbin and /usr/sbin may not necessarily be on $PATH; we don't
            # use the tools dpkg gets from there.
            "--force-bad-path",
            # We check the package architecture ourselves in audit().
            "--force-architecture",
            "--instdir", inst_dir,
            "--admindir", os.path.join(inst_dir, ".click"),
            "--path-exclude", "*/.click/*",
            "--log", os.path.join(root_click, "log"),
            "--no-triggers",
            "--install", path,
        ]
        with open(path, "rb") as fd:
            env = dict(os.environ)
            preloads = [self._preload_path()]
            if "LD_PRELOAD" in env:
                preloads.append(env["LD_PRELOAD"])
            env["LD_PRELOAD"] = " ".join(preloads)
            env["CLICK_BASE_DIR"] = self.db.props.overlay
            env["CLICK_PACKAGE_PATH"] = path
            env["CLICK_PACKAGE_FD"] = str(fd.fileno())
            env.pop("HOME", None)
            kwargs = {}
            if sys.version >= "3.2":
                kwargs["pass_fds"] = (fd.fileno(),)
            subprocess.check_call(
                command, preexec_fn=partial(self._install_preexec, inst_dir),
                env=env, **kwargs)
        for dirpath, dirnames, filenames in os.walk(inst_dir):
            for entry in dirnames + filenames:
                entry_path = os.path.join(dirpath, entry)
                entry_mode = os.stat(entry_path).st_mode
                new_entry_mode = entry_mode | stat.S_IRGRP | stat.S_IROTH
                if entry_mode & stat.S_IXUSR:
                    new_entry_mode |= stat.S_IXGRP | stat.S_IXOTH
                if new_entry_mode != entry_mode:
                    try:
                        os.chmod(entry_path, new_entry_mode)
                    except OSError:
                        pass

        current_path = os.path.join(package_dir, "current")

        if os.path.islink(current_path):
            old_version = os.readlink(current_path)
            if "/" in old_version:
                old_version = None
        else:
            old_version = None
        Click.package_install_hooks(
            self.db, package_name, old_version, package_version,
            user_name=None)

        new_path = os.path.join(package_dir, "current.new")
        Click.symlink_force(package_version, new_path)
        if os.geteuid() == 0:
            # shutil.chown would be more convenient, but it doesn't support
            # follow_symlinks=False in Python 3.3.
            # http://bugs.python.org/issue18108
            pw = pwd.getpwnam("clickpkg")
            os.chown(new_path, pw.pw_uid, pw.pw_gid, follow_symlinks=False)
        os.rename(new_path, current_path)

        return package_name, package_version, old_version

    def install(self, path, user=None, all_users=False):
        package_name, package_version, old_version = self._unpack(
            path, user=user, all_users=all_users)

        if user is not None or all_users:
            if all_users:
                registry = Click.User.for_all_users(self.db)
            else:
                registry = Click.User.for_user(self.db, name=user)
            registry.set_version(package_name, package_version)

        if old_version is not None:
            self.db.maybe_remove(package_name, old_version)
