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


from collections import Sequence
import os
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
    def __init__(self, root):
        self.root = root

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
        self._db.append(ClickSingleDB(root))

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
        """Return current package versions in only this database.

        If all_versions=True, return all versions, not just current ones.
        """
        seen = set()
        for db in reversed(self._db):
            for package, version, path in \
                    db.packages(all_versions=all_versions):
                if all_versions:
                    seen_id = (package, version)
                else:
                    seen_id = package
                if seen_id not in seen:
                    yield package, version, path
                    seen.add(seen_id)
