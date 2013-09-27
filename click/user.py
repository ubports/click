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

"""Registry of user-installed Click packages.

Click packages are installed into per-package/version directories, so it is
quite feasible for more than one version of a given package to be installed
at once, allowing per-user installations; for instance, one user of a tablet
may be uncomfortable with granting some new permission to an app, but
another may be just fine with it.  To make this useful, we also need a
registry of which users have which versions of each package installed.

We might have chosen to use a proper database.  However, a major goal of
Click packages is extreme resilience; we must never get into a situation
where some previous error in package installation or removal makes it hard
for the user to install or remove other packages.  Furthermore, the simpler
application execution can be the better.  So, instead, we use just about the
simplest "database" format imaginable: a directory of symlinks per user.
"""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'ClickUser',
    'ClickUsers',
    ]

from collections import Mapping
from contextlib import contextmanager
import os
import pwd

from click import osextras


# Pseudo-usernames selected to be invalid as a real username, and alluding
# to group syntaxes used in other systems.
ALL_USERS = "@all"
GC_IN_USE_USER = "@gcinuse"

# Pseudo-versions.  In this case the @ doesn't allude to group syntaxes, but
# since @ is conveniently invalid in version numbers we stick to the same
# prefix used for pseudo-usernames.
HIDDEN_VERSION = "@hidden"


def _db_top(root):
    # This is deliberately outside any user's home directory so that it can
    # safely be iterated etc. as root.
    return os.path.join(root, ".click", "users")


def _db_for_user(root, user):
    return os.path.join(_db_top(root), user)


class ClickUsers(Mapping):
    def __init__(self, db):
        self.db = db
        self._click_pw = None

    @property
    def click_pw(self):
        if self._click_pw is None:
            self._click_pw = pwd.getpwnam("clickpkg")
        return self._click_pw

    def _ensure_db(self):
        create = []
        # Only modify the last database.
        path = _db_top(self.db.overlay)
        while not os.path.exists(path):
            create.append(path)
            path = os.path.dirname(path)
        for path in reversed(create):
            os.mkdir(path)
            if os.geteuid() == 0:
                pw = self.click_pw
                os.chown(path, pw.pw_uid, pw.pw_gid)

    def __iter__(self):
        seen = set()
        for db in self.db:
            user_db = _db_top(db.root)
            for entry in osextras.listdir_force(user_db):
                if entry in seen:
                    continue
                if os.path.isdir(os.path.join(user_db, entry)):
                    seen.add(entry)
                    yield entry

    def __len__(self):
        count = 0
        for entry in self:
            count += 1
        return count

    def __getitem__(self, user):
        for db in self.db:
            path = _db_for_user(db.root, user)
            if os.path.isdir(path):
                # We only require the user path to exist in any database; it
                # doesn't matter which.
                return ClickUser(self.db, user=user)
        else:
            raise KeyError("User %s does not exist in any database" % user)


class ClickUser(Mapping):
    """Database of package versions registered for a single user."""

    def __init__(self, db, user=None, all_users=False):
        if user is None:
            user = pwd.getpwuid(os.getuid()).pw_name
        self.db = db
        self.user = user
        self.all_users = all_users
        if self.all_users:
            self.user = ALL_USERS
        self._users = None
        self._user_pw = None
        self._dropped_privileges_count = 0
        self._old_umask = None

    @property
    def pseudo_user(self):
        return self.user.startswith("@")

    @property
    def user_pw(self):
        assert not self.pseudo_user
        if self._user_pw is None:
            self._user_pw = pwd.getpwnam(self.user)
        return self._user_pw

    @property
    def overlay_db(self):
        # Only modify the last database.
        return _db_for_user(self.db.overlay, self.user)

    def _ensure_db(self):
        if self._users is None:
            self._users = ClickUsers(self.db)
        self._users._ensure_db()
        path = self.overlay_db
        if not os.path.exists(path):
            os.mkdir(path)
            if os.geteuid() == 0 and not self.pseudo_user:
                pw = self.user_pw
                os.chown(path, pw.pw_uid, pw.pw_gid)

    def _drop_privileges(self):
        if (self._dropped_privileges_count == 0 and os.getuid() == 0 and
                not self.pseudo_user):
            # We don't bother with setgroups here; we only need the
            # user/group of created filesystem nodes to be correct.
            pw = self.user_pw
            os.setegid(pw.pw_gid)
            os.seteuid(pw.pw_uid)
            self._old_umask = os.umask(osextras.get_umask() | 0o002)
        self._dropped_privileges_count += 1

    def _regain_privileges(self):
        self._dropped_privileges_count -= 1
        if (self._dropped_privileges_count == 0 and os.getuid() == 0 and
                not self.pseudo_user):
            if self._old_umask is not None:
                os.umask(self._old_umask)
            os.seteuid(0)
            os.setegid(0)

    # Note on privilege handling:
    # We can normally get away without dropping privilege when reading, but
    # some filesystems are strict about how much they let root work with
    # user files (e.g. NFS root_squash).  It is better to play it safe and
    # drop privileges for any operations on the user's database.
    @contextmanager
    def _dropped_privileges(self):
        self._drop_privileges()
        try:
            yield
        finally:
            self._regain_privileges()

    def _is_valid_link(self, path):
        return os.path.islink(path) and not os.readlink(path).startswith("@")

    def __iter__(self):
        # We cannot be lazy here, because otherwise calling code may
        # unwittingly end up with dropped privileges.
        entries = []
        hidden = set()
        with self._dropped_privileges():
            for db in reversed(self.db):
                user_db = _db_for_user(db.root, self.user)
                for entry in osextras.listdir_force(user_db):
                    if entry in entries or entry in hidden:
                        continue
                    path = os.path.join(user_db, entry)
                    if self._is_valid_link(path):
                        entries.append(entry)
                    elif os.path.islink(path):
                        hidden.add(entry)
                if not self.all_users:
                    all_users_db = _db_for_user(db.root, ALL_USERS)
                    for entry in osextras.listdir_force(all_users_db):
                        if entry in entries or entry in hidden:
                            continue
                        path = os.path.join(all_users_db, entry)
                        if self._is_valid_link(path):
                            entries.append(entry)
                        elif os.path.islink(path):
                            hidden.add(entry)

        return iter(entries)

    def __len__(self):
        count = 0
        for entry in self:
            count += 1
        return count

    def __getitem__(self, package):
        for db in reversed(self.db):
            user_db = _db_for_user(db.root, self.user)
            path = os.path.join(user_db, package)
            with self._dropped_privileges():
                if self._is_valid_link(path):
                    return os.path.basename(os.readlink(path))
                elif os.path.islink(path):
                    raise KeyError(
                        "%s is hidden for user %s" % (package, self.user))
            all_users_db = _db_for_user(db.root, ALL_USERS)
            path = os.path.join(all_users_db, package)
            if self._is_valid_link(path):
                return os.path.basename(os.readlink(path))
            elif os.path.islink(path):
                raise KeyError("%s is hidden for all users" % package)
        else:
            raise KeyError(
                "%s does not exist in any database for user %s" %
                (package, self.user))

    def set_version(self, package, version):
        # Circular import.
        from click.hooks import package_install_hooks

        # Only modify the last database.
        user_db = self.overlay_db
        path = os.path.join(user_db, package)
        new_path = os.path.join(user_db, ".%s.new" % package)
        self._ensure_db()
        old_version = self.get(package)
        with self._dropped_privileges():
            target = self.db.path(package, version)
            done = False
            if self._is_valid_link(path):
                osextras.unlink_force(path)
                if self.get(path) == version:
                    done = True
            if not done:
                osextras.symlink_force(target, new_path)
                os.rename(new_path, path)
        if not self.pseudo_user:
            package_install_hooks(
                self.db, package, old_version, version, user=self.user)

    def remove(self, package):
        # Circular import.
        from click.hooks import package_remove_hooks

        # Only modify the last database.
        user_db = self.overlay_db
        path = os.path.join(user_db, package)
        with self._dropped_privileges():
            if self._is_valid_link(path):
                old_version = os.path.basename(os.readlink(path))
                osextras.unlink_force(path)
            else:
                try:
                    old_version = self[package]
                    self._ensure_db()
                    osextras.symlink_force(HIDDEN_VERSION, path)
                except KeyError:
                    raise KeyError(
                        "%s does not exist in any database for user %s" %
                        (package, self.user))
        if not self.pseudo_user:
            package_remove_hooks(self.db, package, old_version, user=self.user)

    def path(self, package):
        for db in reversed(self.db):
            user_db = _db_for_user(db.root, self.user)
            path = os.path.join(user_db, package)
            if self._is_valid_link(path):
                return path
            elif os.path.islink(path):
                raise KeyError(
                    "%s is hidden for user %s" % (package, self.user))
            all_users_db = _db_for_user(db.root, ALL_USERS)
            path = os.path.join(all_users_db, package)
            if self._is_valid_link(path):
                return path
            elif os.path.islink(path):
                raise KeyError("%s is hidden for all users" % package)
        else:
            raise KeyError(
                "%s does not exist in any database for user %s" %
                (package, self.user))

    def removable(self, package):
        user_db = self.overlay_db
        path = os.path.join(user_db, package)
        if os.path.exists(path):
            return True
        elif os.path.islink(path):
            # Already hidden.
            return False
        all_users_db = _db_for_user(self.db.overlay, ALL_USERS)
        path = os.path.join(all_users_db, package)
        if self._is_valid_link(path):
            return True
        elif os.path.islink(path):
            # Already hidden.
            return False
        if package in self:
            # Not in overlay database, but can be hidden.
            return True
        else:
            return False
