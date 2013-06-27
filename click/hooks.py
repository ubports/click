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
    "run_hooks",
    ]

import json
import os
import subprocess

from debian.deb822 import Deb822

from click import osextras


HOOKS_DIR = "/usr/share/click/hooks"


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


class ClickHook(Deb822):
    def __init__(self, name, sequence=None, fields=None, encoding="utf-8"):
        super(ClickHook, self).__init__(
            sequence=sequence, fields=fields, encoding=encoding)
        self.name = name

    @classmethod
    def open(cls, name):
        try:
            with open(os.path.join(HOOKS_DIR, "%s.hook" % name)) as f:
                return cls(name, f)
        except IOError:
            raise KeyError("No click hook '%s' installed" % name)

    def _run_commands(self):
        if "exec" in self:
            subprocess.check_call(self["exec"], shell=True)
        if self.get("trigger", "no") == "yes":
            raise NotImplementedError("'Trigger: yes' not yet implemented")

    def install(self, root, package, version, relative_path):
        osextras.symlink_force(
            os.path.join(root, package, version, relative_path),
            self["pattern"] % package)
        self._run_commands()

    def remove(self, package):
        osextras.unlink_force(self["pattern"] % package)
        self._run_commands()

    def _all_packages(self, root):
        for package in osextras.listdir_force(root):
            current_path = os.path.join(root, package, "current")
            if os.path.islink(current_path):
                version = os.readlink(current_path)
                if "/" not in version:
                    yield package, version

    def _relevant_packages(self, root):
        for package, version in self._all_packages(root):
            manifest = _read_manifest_hooks(root, package, version)
            if self.name in manifest:
                yield package, version, manifest[self.name]

    def install_all(self, root):
        for package, version, relative_path in self._relevant_packages(root):
            self.install(root, package, version, relative_path)

    def remove_all(self, root):
        for package, version, relative_path in self._relevant_packages(root):
            self.remove(package)


def run_hooks(root, package, old_version, new_version):
    old_manifest = _read_manifest_hooks(root, package, old_version)
    new_manifest = _read_manifest_hooks(root, package, new_version)

    for name in sorted(set(old_manifest) - set(new_manifest)):
        try:
            hook = ClickHook.open(name)
        except KeyError:
            pass
        hook.remove(package)

    for name, relative_path in sorted(new_manifest.items()):
        try:
            hook = ClickHook.open(name)
        except KeyError:
            pass
        hook.install(root, package, new_version, relative_path)
