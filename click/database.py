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

"""Click databases."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    "ClickDB",
    ]


from collections import Sequence, defaultdict
import io
import json
import os
import shutil
import subprocess
import sys

try:
    from configparser import Error as ConfigParserError
    if sys.version < "3.2":
        from configparser import SafeConfigParser as ConfigParser
    else:
        from configparser import ConfigParser
except ImportError:
    from ConfigParser import Error as ConfigParserError
    from ConfigParser import SafeConfigParser as ConfigParser

from click import osextras
from click.paths import db_dir


class ClickSingleDB:
    def __init__(self, root, master_db):
        self.root = root
        self.master_db = master_db

    def path(self, package, version):
        """Look up a package and version in only this database."""
        try_path = os.path.join(self.root, package, version)
        if os.path.exists(try_path):
            return try_path
        else:
            raise KeyError(
                "%s %s does not exist in %s" % (package, version, self.root))

    def packages(self, all_versions=False):
        """Return all current package versions in only this database.

        If all_versions=True, return all versions, not just current ones.
        """
        for package in sorted(osextras.listdir_force(self.root)):
            if package == ".click":
                continue
            if all_versions:
                package_path = os.path.join(self.root, package)
                for version in sorted(osextras.listdir_force(package_path)):
                    version_path = os.path.join(package_path, version)
                    if (os.path.islink(version_path) or
                            not os.path.isdir(version_path)):
                        continue
                    yield package, version, version_path
            else:
                current_path = os.path.join(self.root, package, "current")
                if os.path.islink(current_path):
                    version = os.readlink(current_path)
                    if "/" not in version:
                        yield package, version, current_path

    def _app_running(self, package, app_name, version):
        app_id = "%s_%s_%s" % (package, app_name, version)
        command = ["upstart-app-pid", app_id]
        with open("/dev/null", "w") as devnull:
            return subprocess.call(command, stdout=devnull) == 0

    def _any_app_running(self, package, version):
        if not osextras.find_on_path("upstart-app-pid"):
            return False
        manifest_path = os.path.join(
            self.path(package, version), ".click", "info",
            "%s.manifest" % package)
        try:
            with io.open(manifest_path, encoding="UTF-8") as manifest:
                manifest_json = json.load(manifest)
            for app_name in manifest_json.get("hooks", {}):
                if self._app_running(package, app_name, version):
                    return True
        except Exception:
            pass
        return False

    def _remove_unless_running(self, package, version, verbose=False):
        # Circular imports.
        from click.user import ClickUser, GC_IN_USE_USER

        if self._any_app_running(package, version):
            gc_in_use_user_db = ClickUser(self.master_db, user=GC_IN_USE_USER)
            gc_in_use_user_db[package] = version
            return

        version_path = self.path(package, version)
        if verbose:
            print("Removing %s" % version_path)
        shutil.rmtree(version_path, ignore_errors=True)

        package_path = os.path.join(self.root, package)
        current_path = os.path.join(package_path, "current")
        if (os.path.islink(current_path) and
                os.readlink(current_path) == version):
            os.unlink(current_path)
            # TODO: Perhaps we should relink current to the latest remaining
            # version.  However, that requires version comparison, and it's
            # not clear whether it's worth it given that current is mostly
            # superseded by user registration.
        if not os.listdir(package_path):
            os.rmdir(package_path)

    def maybe_remove(self, package, version):
        """Remove a package version if it is not in use.

        "In use" may mean registered for another user, or running.  In the
        latter case we construct a fake registration so that we can tell the
        difference later between a package version that was in use at the
        time of removal and one that was never registered for any user.

        (This is unfortunately complex, and perhaps some day we can require
        that installations always have some kind of registration to avoid
        this complexity.)
        """
        # Circular imports.
        from click.user import ClickUsers, GC_IN_USE_USER

        for user_name, user_db in ClickUsers(self.master_db).items():
            if user_db.get(package) == version:
                if user_name == GC_IN_USE_USER:
                    # Previously running; we'll check this again shortly.
                    del user_db[package]
                else:
                    # In use.
                    return

        self._remove_unless_running(package, version)

    def gc(self, verbose=True):
        """Remove package versions with no user registrations.

        To avoid accidentally removing packages that were installed without
        ever having a user registration, we only garbage-collect packages
        that were not removed by ClickSingleDB.maybe_remove due to having a
        running application at the time.

        (This is unfortunately complex, and perhaps some day we can require
        that installations always have some kind of registration to avoid
        this complexity.)
        """
        # Circular import.
        from click.user import ClickUser, ClickUsers, GC_IN_USE_USER

        user_reg = defaultdict(set)
        gc_in_use = defaultdict(set)
        for user_name, user_db in ClickUsers(self.master_db).items():
            for package, version in user_db.items():
                if user_name == GC_IN_USE_USER:
                    gc_in_use[package].add(version)
                else:
                    user_reg[package].add(version)

        gc_in_use_user_db = ClickUser(self.master_db, user=GC_IN_USE_USER)
        for package in sorted(osextras.listdir_force(self.root)):
            if package == ".click":
                continue
            package_path = os.path.join(self.root, package)
            for version in sorted(osextras.listdir_force(package_path)):
                if version in user_reg[package]:
                    # In use.
                    continue
                if version not in gc_in_use[package]:
                    version_path = os.path.join(package_path, version)
                    if verbose:
                        print(
                            "Not removing %s (never registered)." %
                            version_path)
                    continue
                del gc_in_use_user_db[package]
                self._remove_unless_running(package, version, verbose=verbose)


class ClickDB(Sequence):
    def __init__(self, extra_root=None, use_system=True, override_db_dir=None):
        if override_db_dir is None:
            override_db_dir = db_dir
        self._db = []
        if use_system:
            for entry in sorted(osextras.listdir_force(override_db_dir)):
                if not entry.endswith(".conf"):
                    continue
                path = os.path.join(override_db_dir, entry)
                config = ConfigParser()
                try:
                    config.read(path)
                    root = config.get("Click Database", "root")
                except ConfigParserError as e:
                    print(e, file=sys.stderr)
                    continue
                self.add(root)
        if extra_root is not None:
            self.add(extra_root)

    def __getitem__(self, key):
        return self._db[key]

    def __len__(self):
        return len(self._db)

    def add(self, root):
        self._db.append(ClickSingleDB(root, self))

    @property
    def overlay(self):
        """Return the directory where changes should be written."""
        return self._db[-1].root

    def path(self, package, version):
        """Look up a package and version in all databases."""
        for db in reversed(self._db):
            try:
                return db.path(package, version)
            except KeyError:
                pass
        else:
            raise KeyError(
                "%s %s does not exist in any database" % (package, version))

    def packages(self, all_versions=False):
        """Return current package versions in all databases.

        If all_versions=True, return all versions, not just current ones.
        """
        seen = set()
        for db in reversed(self._db):
            writeable = db is self._db[-1]
            for package, version, path in \
                    db.packages(all_versions=all_versions):
                if all_versions:
                    seen_id = (package, version)
                else:
                    seen_id = package
                if seen_id not in seen:
                    yield package, version, path, writeable
                    seen.add(seen_id)

    def maybe_remove(self, package, version):
        self._db[-1].maybe_remove(package, version)

    def gc(self, verbose=True):
        self._db[-1].gc(verbose=verbose)
