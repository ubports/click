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

"""Click package hooks.

See doc/hooks.rst for the draft specification.
"""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "ClickHook",
    "package_install_hooks",
    ]

from functools import partial
import grp
import json
import os
import pwd
import re
from string import Formatter
import subprocess

from debian.deb822 import Deb822

from click import osextras
from click.paths import hooks_dir
from click.user import ClickUser, ClickUsers


def _read_manifest_hooks(root, package, version):
    if version is None:
        return {}
    manifest_path = os.path.join(
        root, package, version, ".click", "info", "%s.manifest" % package)
    try:
        with open(manifest_path) as manifest:
            return json.load(manifest).get("hooks", {})
    except IOError:
        return {}


class ClickPatternFormatter(Formatter):
    """A Formatter that handles simple $-expansions.

    `${key}` is replaced by the value of the `key` argument; `$$` is
    replaced by `$`.  Any `$` character not followed by `{...}` is preserved
    intact.
    """
    _expansion_re = re.compile(r"\${(.*?)}")

    def parse(self, format_string):
        while True:
            match = self._expansion_re.search(format_string)
            if match is None:
                if format_string:
                    yield format_string, None, None, None
                return
            start, end = match.span()
            yield format_string[:match.start()], match.group(1), "", None
            format_string = format_string[match.end():]

    def get_field(self, field_name, args, kwargs):
        value = kwargs.get(field_name)
        if value is None:
            value = ""
        return value, field_name


class ClickHook(Deb822):
    _formatter = ClickPatternFormatter()

    def __init__(self, name, sequence=None, fields=None, encoding="utf-8"):
        super(ClickHook, self).__init__(
            sequence=sequence, fields=fields, encoding=encoding)
        self.name = name

    @classmethod
    def open(cls, name):
        try:
            with open(os.path.join(hooks_dir, "%s.hook" % name)) as f:
                return cls(name, f)
        except IOError:
            raise KeyError("No click hook '%s' installed" % name)

    @property
    def user_level(self):
        return self.get("user-level", "no") == "yes"

    @property
    def single_version(self):
        return self.user_level or self.get("single-version", "no") == "yes"

    def app_id(self, package, version, app_name):
        # TODO: perhaps this check belongs further up the stack somewhere?
        if "_" in app_name or "/" in app_name:
            raise ValueError(
                "Application name '%s' may not contain _ or / characters" %
                app_name)
        return "%s_%s_%s" % (package, app_name, version)

    def _user_home(self, user):
        if user is None:
            return None
        # TODO: make robust against removed users
        # TODO: caching
        return pwd.getpwnam(user).pw_dir

    def pattern(self, package, version, app_name, user=None):
        app_id = self.app_id(package, version, app_name)
        return self._formatter.format(
            self["pattern"], id=app_id, user=user, home=self._user_home(user))

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
        os.environ["HOME"] = pw.pw_dir

    def _run_commands_user(self, user=None):
        if self.user_level:
            return user
        else:
            return self["user"]

    def _run_commands(self, user=None):
        if "exec" in self:
            drop_privileges = partial(
                self._drop_privileges, self._run_commands_user(user=user))
            subprocess.check_call(
                self["exec"], preexec_fn=drop_privileges, shell=True)
        if self.get("trigger", "no") == "yes":
            raise NotImplementedError("'Trigger: yes' not yet implemented")

    def install(self, root, package, version, app_name, relative_path,
                user=None):
        # Prepare paths.
        if self.user_level:
            user_db = ClickUser(root, user=user)
            target = os.path.join(user_db.path(package), relative_path)
            link = self.pattern(package, version, app_name, user=user)
        else:
            target = os.path.join(root, package, version, relative_path)
            link = self.pattern(package, version, app_name, user=None)
        link_dir = os.path.dirname(link)

        # Remove previous versions if necessary.
        if self.single_version:
            previous_prefix = "%s_%s_" % (package, app_name)
            for previous_entry in osextras.listdir_force(link_dir):
                if previous_entry.startswith(previous_prefix):
                    osextras.unlink_force(
                        os.path.join(link_dir, previous_entry))

        # Install new links and run commands.
        if self.user_level:
            with user_db._dropped_privileges():
                osextras.ensuredir(link_dir)
                osextras.symlink_force(target, link)
        else:
            osextras.symlink_force(target, link)
        self._run_commands(user=user)

    def remove(self, package, version, app_name, user=None):
        osextras.unlink_force(
            self.pattern(package, version, app_name, user=user))
        self._run_commands(user=user)

    def _all_packages(self, root):
        """Return an iterable of all unpacked packages.

        If running a user-level hook, this returns (package, version, user)
        for the current version of each package registered for each user.

        If running a system-level hook, this returns (package, version,
        None) for each version of each unpacked package.
        """
        if self.user_level:
            for user, user_db in ClickUsers(root).items():
                for package, version in user_db.items():
                    yield package, version, user
        else:
            for package in osextras.listdir_force(root):
                current_path = os.path.join(root, package, "current")
                if os.path.islink(current_path):
                    version = os.readlink(current_path)
                    if "/" not in version:
                        yield package, version, None

    def _relevant_apps(self, root):
        """Return an iterable of all applications relevant for this hook."""
        for package, version, user in self._all_packages(root):
            manifest = _read_manifest_hooks(root, package, version)
            for app_name, hooks in manifest.items():
                if self.name in hooks:
                    yield package, version, app_name, user, hooks[self.name]

    def install_all(self, root):
        for package, version, app_name, user, relative_path in (
                self._relevant_apps(root)):
            self.install(
                root, package, version, app_name, relative_path, user=user)

    def remove_all(self, root):
        for package, version, app_name, user, _ in self._relevant_apps(root):
            self.remove(package, version, app_name, user=user)


def _app_hooks(hooks):
    items = set()
    for app_name in hooks:
        for hook_name in hooks[app_name]:
            items.add((app_name, hook_name))
    return items


def package_install_hooks(root, package, old_version, new_version, user=None):
    """Run hooks following installation of a Click package.

    If user is None, only run system-level hooks.  If user is not None, only
    run user-level hooks for that user.
    """
    old_manifest = _read_manifest_hooks(root, package, old_version)
    new_manifest = _read_manifest_hooks(root, package, new_version)

    # Remove any targets for single-version hooks that were in the old
    # manifest but not the new one.
    for app_name, hook_name in sorted(
            _app_hooks(old_manifest) - _app_hooks(new_manifest)):
        try:
            hook = ClickHook.open(hook_name)
        except KeyError:
            continue
        if hook.user_level != (user is not None):
            continue
        if hook.single_version:
            hook.remove(package, old_version, app_name, user=user)

    for app_name, app_hooks in sorted(new_manifest.items()):
        for hook_name, relative_path in sorted(app_hooks.items()):
            try:
                hook = ClickHook.open(hook_name)
            except KeyError:
                continue
            if hook.user_level != (user is not None):
                continue
            hook.install(
                root, package, new_version, app_name, relative_path, user=user)
