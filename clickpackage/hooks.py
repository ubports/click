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
    ]

import json
import os
import subprocess

from debian.deb822 import Deb822

from clickpackage import osextras


HOOKS_DIR = "/usr/share/click-package/hooks"


class ClickHook(Deb822):
    @classmethod
    def open(cls, name):
        try:
            with open(os.path.join(HOOKS_DIR, "%s.hook" % name)) as f:
                return cls(f)
        except IOError:
            raise KeyError("No click-package hook '%s' installed" % name)

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


def _read_manifest_hooks(root, package, version):
    if version is None:
        return {}
    manifest_path = os.path.join(root, package, version, "manifest.json")
    try:
        with open(manifest_path) as manifest:
            return json.load(manifest).get("hooks", {})
    except IOError:
        return {}


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
