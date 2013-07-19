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

from collections import Mapping, MutableMapping
from contextlib import contextmanager
import os
import pwd

from click import osextras


def _db_top(root):
    # This is deliberately outside any user's home directory so that it can
    # safely be iterated etc. as root.
    return os.path.join(root, ".click", "users")


def _db_for_user(root, user):
    return os.path.join(_db_top(root), user)


class ClickUsers(Mapping):
    def __init__(self, root):
        self.root = root
        self._click_pw = None
        # This is deliberately outside any user's home directory so that it
        # can safely be iterated etc. as root.
        self._db = _db_top(self.root)

    @property
    def click_pw(self):
        if self._click_pw is None:
            self._click_pw = pwd.getpwnam("clickpkg")
        return self._click_pw

    def _ensure_db(self):
        create = []
        path = self._db
        while not os.path.exists(path):
            create.append(path)
            path = os.path.dirname(path)
        for path in reversed(create):
            os.mkdir(path)
            if os.getuid() == 0:
                pw = self.click_pw
                os.chown(path, pw.pw_uid, pw.pw_gid)

    def __iter__(self):
        for entry in osextras.listdir_force(self._db):
            if os.path.isdir(os.path.join(self._db, entry)):
                yield entry

    def __len__(self):
        count = 0
        for entry in self:
            count += 1
        return count

    def __getitem__(self, user):
        path = _db_for_user(self.root, user)
        if os.path.isdir(path):
            return ClickUser(self.root, user=user)
        else:
            raise KeyError


class ClickUser(MutableMapping):
    def __init__(self, root, user=None):
        self.root = root
        if user is None:
            user = pwd.getpwuid(os.getuid()).pw_name
        self.user = user
        self._users = None
        self._user_pw = None
        self._db = _db_for_user(self.root, self.user)
        self._dropped_privileges_count = 0

    @property
    def user_pw(self):
        if self._user_pw is None:
            self._user_pw = pwd.getpwnam(self.user)
        return self._user_pw

    def _ensure_db(self):
        if self._users is None:
            self._users = ClickUsers(self.root)
        self._users._ensure_db()
        if not os.path.exists(self._db):
            os.mkdir(self._db)
            if os.getuid() == 0:
                pw = self.user_pw
                os.chown(self._db, pw.pw_uid, pw.pw_gid)

    def _drop_privileges(self):
        if self._dropped_privileges_count == 0 and os.getuid() == 0:
            # We don't bother with setgroups here; we only need the
            # user/group of created filesystem nodes to be correct.
            pw = self.user_pw
            os.setegid(pw.pw_gid)
            os.seteuid(pw.pw_uid)
        self._dropped_privileges_count += 1

    def _regain_privileges(self):
        self._dropped_privileges_count -= 1
        if self._dropped_privileges_count == 0 and os.getuid() == 0:
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

    def __iter__(self):
        with self._dropped_privileges():
            for entry in osextras.listdir_force(self._db):
                if os.path.islink(os.path.join(self._db, entry)):
                    yield entry

    def __len__(self):
        count = 0
        for entry in self:
            count += 1
        return count

    def __getitem__(self, package):
        path = os.path.join(self._db, package)
        with self._dropped_privileges():
            if os.path.islink(path):
                return os.path.basename(os.readlink(path))
            else:
                raise KeyError

    def __setitem__(self, package, version):
        # Circular import.
        from click.hooks import package_install_hooks

        path = os.path.join(self._db, package)
        new_path = os.path.join(self._db, ".%s.new" % package)
        self._ensure_db()
        old_version = self.get(package)
        with self._dropped_privileges():
            target = os.path.join(self.root, package, version)
            if not os.path.exists(target):
                raise ValueError("%s does not exist" % target)
            osextras.symlink_force(target, new_path)
            os.rename(new_path, path)
        package_install_hooks(
            self.root, package, old_version, version, user=self.user)

    def __delitem__(self, package):
        path = os.path.join(self._db, package)
        with self._dropped_privileges():
            if os.path.islink(path):
                osextras.unlink_force(path)
            else:
                raise KeyError
        # TODO: run hooks for removal

    def path(self, package):
        return os.path.join(self._db, package)
