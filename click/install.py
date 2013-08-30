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
    ]


from functools import partial
import grp
import inspect
import json
import os
import pwd
import subprocess
import sys

from contextlib import closing

from debian.debfile import DebFile as _DebFile
from debian.debian_support import Version

from click import osextras
from click.hooks import package_install_hooks
from click.paths import frameworks_dir, preload_path
from click.preinst import static_preinst_matches
from click.user import ClickUser
from click.versions import spec_version


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


class ClickInstallerPermissionDenied(Exception):
    pass


class ClickInstaller:
    def __init__(self, root, force_missing_framework=False):
        self.root = root
        self.force_missing_framework = force_missing_framework

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

    def _has_framework(self, name):
        return os.path.exists(os.path.join(
            frameworks_dir, "%s.framework" % name))

    def audit_control(self, control_part):
        """Check that all requirements on the control part are met.

        Returns the package name.
        """
        control_fields = control_part.debcontrol()

        try:
            click_version = Version(control_fields["Click-Version"])
        except KeyError:
            raise ValueError("No Click-Version field")
        if click_version > spec_version:
            raise ValueError(
                "Click-Version: %s newer than maximum supported version %s" %
                (click_version, spec_version))

        for field in (
            "Pre-Depends", "Depends", "Recommends", "Suggests", "Enhances",
            "Conflicts", "Breaks",
            "Provides",
        ):
            if field in control_fields:
                raise ValueError(
                    "%s field is forbidden in Click packages" % field)

        scripts = control_part.scripts()
        if ("preinst" in scripts and
                static_preinst_matches(scripts["preinst"])):
            scripts.pop("preinst", None)
        if scripts:
            raise ValueError(
                "Maintainer scripts are forbidden in Click packages "
                "(found: %s)" %
                " ".join(sorted(scripts)))

        if not control_part.has_file("manifest"):
            raise ValueError("Package has no manifest")
        with control_part.get_file("manifest", encoding="UTF-8") as f:
            manifest = json.loads(f.read())

        try:
            package_name = manifest["name"]
        except KeyError:
            raise ValueError('No "name" entry in manifest')
        # TODO: perhaps just do full name validation?
        if "/" in package_name:
            raise ValueError(
                'Invalid character "/" in "name" entry: %s' % package_name)
        if "_" in package_name:
            raise ValueError(
                'Invalid character "_" in "name" entry: %s' % package_name)

        try:
            package_version = manifest["version"]
        except KeyError:
            raise ValueError('No "version" entry in manifest')
        # TODO: perhaps just do full version validation?
        if "/" in package_version:
            raise ValueError(
                'Invalid character "/" in "version" entry: %s' %
                package_version)
        if "_" in package_version:
            raise ValueError(
                'Invalid character "_" in "version" entry: %s' %
                package_version)

        try:
            framework = manifest["framework"]
        except KeyError:
            raise ValueError('No "framework" entry in manifest')
        if (not self.force_missing_framework and
                not self._has_framework(framework)):
            raise ValueError(
                'Framework "%s" not present on system' % framework)

        return package_name, package_version

    def audit(self, path):
        with closing(DebFile(filename=path)) as package:
            return self.audit_control(package.control)

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
                "No permission to write to %s as clickpkg user" % path)

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

    def install(self, path, user=None):
        package_name, package_version = self.audit(path)
        package_dir = os.path.join(self.root, package_name)
        inst_dir = os.path.join(package_dir, package_version)
        assert os.path.dirname(os.path.dirname(inst_dir)) == self.root

        self._check_write_permissions(self.root)
        root_click = os.path.join(self.root, ".click")
        if not os.path.exists(root_click):
            os.makedirs(root_click)
            if os.geteuid() == 0:
                pw = pwd.getpwnam("clickpkg")
                os.chown(root_click, pw.pw_uid, pw.pw_gid)

        # TODO: sandbox so that this can only write to the unpack directory
        command = [
            "dpkg",
            "--force-not-root", "--force-bad-path",
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
            env["CLICK_BASE_DIR"] = self.root
            env["CLICK_PACKAGE_PATH"] = path
            env["CLICK_PACKAGE_FD"] = str(fd.fileno())
            env.pop("HOME", None)
            kwargs = {}
            if sys.version >= "3.2":
                kwargs["pass_fds"] = (fd.fileno(),)
            subprocess.check_call(
                command, preexec_fn=partial(self._install_preexec, inst_dir),
                env=env, **kwargs)

        current_path = os.path.join(package_dir, "current")

        if os.path.islink(current_path):
            old_version = os.readlink(current_path)
            if "/" in old_version:
                old_version = None
        else:
            old_version = None
        package_install_hooks(
            self.root, package_name, old_version, package_version)

        new_path = os.path.join(package_dir, "current.new")
        osextras.symlink_force(package_version, new_path)
        if os.geteuid() == 0:
            # shutil.chown would be more convenient, but it doesn't support
            # follow_symlinks=False in Python 3.3.
            # http://bugs.python.org/issue18108
            pw = pwd.getpwnam("clickpkg")
            os.chown(new_path, pw.pw_uid, pw.pw_gid, follow_symlinks=False)
        os.rename(new_path, current_path)

        if user is not None:
            registry = ClickUser(self.root, user)
            registry[package_name] = package_version

        # TODO: garbage-collect old directories
