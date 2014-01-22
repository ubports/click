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
    "run_system_hooks",
    "run_user_hooks",
    ]

from functools import partial
import grp
import io
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


def _read_manifest_hooks(db, package, version):
    if version is None:
        return {}
    try:
        manifest_path = os.path.join(
            db.path(package, version), ".click", "info",
            "%s.manifest" % package)
        with io.open(manifest_path, encoding="UTF-8") as manifest:
            return json.load(manifest).get("hooks", {})
    except (KeyError, IOError):
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

    def possible_expansion(self, s, format_string, *args, **kwargs):
        """Check if s is a possible expansion.

        Any (keyword) arguments have the effect of binding some keys to
        fixed values; unspecified keys may take any value, and will bind
        greedily to the longest possible string.

        If s is a possible expansion, then this method returns a (possibly
        empty) dictionary mapping all the unspecified keys to their bound
        values.  Otherwise, it returns None.
        """
        ret = {}
        regex_pieces = []
        group_names = []
        for literal_text, field_name, format_spec, conversion in \
                self.parse(format_string):
            if literal_text:
                regex_pieces.append(re.escape(literal_text))
            if field_name is not None:
                if field_name in kwargs:
                    regex_pieces.append(re.escape(kwargs[field_name]))
                else:
                    regex_pieces.append("(.*)")
                    group_names.append(field_name)
        match = re.match("^%s$" % "".join(regex_pieces), s)
        if match is None:
            return None
        for group in range(len(group_names)):
            ret[group_names[group]] = match.group(group + 1)
        return ret


class ClickHook(Deb822):
    _formatter = ClickPatternFormatter()

    def __init__(self, db, name, sequence=None, fields=None, encoding="utf-8"):
        super(ClickHook, self).__init__(
            sequence=sequence, fields=fields, encoding=encoding)
        self.db = db
        self.name = name

    @classmethod
    def open(cls, db, name):
        try:
            with open(os.path.join(hooks_dir, "%s.hook" % name)) as f:
                return cls(db, name, f)
        except IOError:
            raise KeyError("No click hook '%s' installed" % name)

    @classmethod
    def open_all(cls, db, hook_name=None):
        for entry in osextras.listdir_force(hooks_dir):
            if not entry.endswith(".hook"):
                continue
            try:
                with open(os.path.join(hooks_dir, entry)) as f:
                    hook = cls(db, entry[:-5], f)
                    if hook_name is None or hook.hook_name == hook_name:
                        yield hook
            except IOError:
                pass

    @property
    def user_level(self):
        return self.get("user-level", "no") == "yes"

    @property
    def single_version(self):
        return self.user_level or self.get("single-version", "no") == "yes"

    @property
    def hook_name(self):
        return self.get("hook-name", self.name)

    def short_app_id(self, package, app_name):
        # TODO: perhaps this check belongs further up the stack somewhere?
        if "_" in app_name or "/" in app_name:
            raise ValueError(
                "Application name '%s' may not contain _ or / characters" %
                app_name)
        return "%s_%s" % (package, app_name)

    def app_id(self, package, version, app_name):
        return "%s_%s" % (self.short_app_id(package, app_name), version)

    def _user_home(self, user):
        if user is None:
            return None
        # TODO: make robust against removed users
        # TODO: caching
        return pwd.getpwnam(user).pw_dir

    def pattern(self, package, version, app_name, user=None):
        app_id = self.app_id(package, version, app_name)
        kwargs = {
            "id": app_id,
            "user": user,
            "home": self._user_home(user),
            }
        if self.single_version:
            kwargs["short-id"] = self.short_app_id(package, app_name)
        return self._formatter.format(self["pattern"], **kwargs).rstrip(os.sep)

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
        os.umask(osextras.get_umask() | 0o002)

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

    def _previous_entries(self, user=None):
        """Find entries that match the structure of our links."""
        link_dir = os.path.dirname(self.pattern("", "", "", user=user))
        # TODO: This only works if the app ID only appears, at most, in the
        # last component of the pattern path.
        for previous_entry in osextras.listdir_force(link_dir):
            previous_path = os.path.join(link_dir, previous_entry)
            previous_exp = self._formatter.possible_expansion(
                previous_path, self["pattern"], user=user,
                home=self._user_home(user))
            if previous_exp is None or "id" not in previous_exp:
                continue
            previous_id = previous_exp["id"]
            try:
                previous_package, previous_app_name, previous_version = (
                    previous_id.split("_", 2))
                yield (
                    previous_path,
                    previous_package, previous_version, previous_app_name)
            except ValueError:
                continue

    def _install_link(self, package, version, app_name, relative_path,
                      user=None, user_db=None):
        """Install a hook symlink.

        This should be called with dropped privileges if necessary.
        """
        if self.user_level:
            target = os.path.join(user_db.path(package), relative_path)
        else:
            target = os.path.join(
                self.db.path(package, version), relative_path)
        link = self.pattern(package, version, app_name, user=user)
        if not os.path.islink(link) or os.readlink(link) != target:
            osextras.ensuredir(os.path.dirname(link))
            osextras.symlink_force(target, link)

    def install_package(self, package, version, app_name, relative_path,
                        user=None):
        if self.user_level:
            user_db = ClickUser(self.db, user=user)
        else:
            assert user is None

        # Remove previous versions if necessary.
        if self.single_version:
            for path, p_package, p_version, p_app_name in \
                    self._previous_entries(user=user):
                if (p_package == package and p_app_name == app_name and
                        p_version != version):
                    osextras.unlink_force(path)

        if self.user_level:
            with user_db._dropped_privileges():
                self._install_link(
                    package, version, app_name, relative_path,
                    user=user, user_db=user_db)
        else:
            self._install_link(package, version, app_name, relative_path)
        self._run_commands(user=user)

    def remove_package(self, package, version, app_name, user=None):
        osextras.unlink_force(
            self.pattern(package, version, app_name, user=user))
        self._run_commands(user=user)

    def _all_packages(self, user=None):
        """Return an iterable of all unpacked packages.

        If running a user-level hook, this returns (package, version, user)
        for the current version of each package registered for each user, or
        only for a single user if user is not None.

        If running a system-level hook, this returns (package, version,
        None) for each version of each unpacked package.
        """
        if self.user_level:
            if user is not None:
                user_db = ClickUser(self.db, user=user)
                for package, version in user_db.items():
                    yield package, version, user
            else:
                for user_name, user_db in ClickUsers(self.db).items():
                    if user_name.startswith("@"):
                        continue
                    for package, version in user_db.items():
                        yield package, version, user_name
        else:
            for package, version, _, _ in self.db.packages():
                yield package, version, None

    def _relevant_apps(self, user=None):
        """Return an iterable of all applications relevant for this hook."""
        for package, version, user_name in self._all_packages(user=user):
            manifest = _read_manifest_hooks(self.db, package, version)
            for app_name, hooks in manifest.items():
                if self.hook_name in hooks:
                    yield (
                        package, version, app_name, user_name,
                        hooks[self.hook_name])

    def install(self, user=None):
        for package, version, app_name, user_name, relative_path in (
                self._relevant_apps(user=user)):
            self.install_package(
                package, version, app_name, relative_path, user=user_name)

    def remove(self, user=None):
        for package, version, app_name, user_name, _ in (
                self._relevant_apps(user=user)):
            self.remove_package(package, version, app_name, user=user_name)

    def sync(self, user=None):
        if self.user_level:
            user_db = ClickUser(self.db, user=user)
        else:
            assert user is None

        seen = set()
        for package, version, app_name, user_name, relative_path in (
                self._relevant_apps(user=user)):
            seen.add((package, version, app_name))
            if self.user_level:
                with user_db._dropped_privileges():
                    self._install_link(
                        package, version, app_name, relative_path,
                        user=user_name, user_db=user_db)
            else:
                self._install_link(package, version, app_name, relative_path)
        for path, package, version, app_name in \
                self._previous_entries(user=user):
            if (package, version, app_name) not in seen:
                osextras.unlink_force(path)
        self._run_commands(user=user)


def _app_hooks(hooks):
    items = set()
    for app_name in hooks:
        for hook_name in hooks[app_name]:
            items.add((app_name, hook_name))
    return items


def package_install_hooks(db, package, old_version, new_version, user=None):
    """Run hooks following installation or upgrade of a Click package.

    If user is None, only run system-level hooks.  If user is not None, only
    run user-level hooks for that user.
    """
    old_manifest = _read_manifest_hooks(db, package, old_version)
    new_manifest = _read_manifest_hooks(db, package, new_version)

    # Remove any targets for single-version hooks that were in the old
    # manifest but not the new one.
    for app_name, hook_name in sorted(
            _app_hooks(old_manifest) - _app_hooks(new_manifest)):
        for hook in ClickHook.open_all(db, hook_name):
            if hook.user_level != (user is not None):
                continue
            if hook.single_version:
                hook.remove_package(package, old_version, app_name, user=user)

    for app_name, app_hooks in sorted(new_manifest.items()):
        for hook_name, relative_path in sorted(app_hooks.items()):
            for hook in ClickHook.open_all(db, hook_name):
                if hook.user_level != (user is not None):
                    continue
                hook.install_package(
                    package, new_version, app_name, relative_path, user=user)


def package_remove_hooks(db, package, old_version, user=None):
    """Run hooks following removal of a Click package.

    If user is None, only run system-level hooks.  If user is not None, only
    run user-level hooks for that user.
    """
    old_manifest = _read_manifest_hooks(db, package, old_version)

    for app_name, app_hooks in sorted(old_manifest.items()):
        for hook_name in sorted(app_hooks):
            for hook in ClickHook.open_all(db, hook_name):
                if hook.user_level != (user is not None):
                    continue
                hook.remove_package(package, old_version, app_name, user=user)


def run_system_hooks(db):
    """Run system-level hooks for all installed packages.

    This is useful when starting up from images with preinstalled packages
    which may not have had their system-level hooks run properly when
    building the image.  It is suitable for running at system startup.
    """
    db.ensure_ownership()
    for hook in ClickHook.open_all(db):
        if not hook.user_level:
            hook.sync()


def run_user_hooks(db, user=None):
    """Run user-level hooks for all packages registered for a user.

    This is useful to catch up with packages that may have been preinstalled
    and registered for all users.  It is suitable for running at session
    startup.
    """
    if user is None:
        user = pwd.getpwuid(os.getuid()).pw_name
    for hook in ClickHook.open_all(db):
        if hook.user_level:
            hook.sync(user=user)
