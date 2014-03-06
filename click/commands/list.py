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

"""List installed Click packages."""

from __future__ import print_function

import io
import json
from optparse import OptionParser
import os
import sys

from gi.repository import Click


def list_packages(options):
    db = Click.DB()
    db.read()
    if options.root is not None:
        db.add(options.root)
    if options.all:
        for inst in db.get_packages(all_versions=True):
            yield (
                inst.props.package, inst.props.version, inst.props.path,
                inst.props.writeable)
    else:
        registry = Click.User.for_user(db, name=options.user)
        for package in sorted(registry.get_package_names()):
            yield (
                package, registry.get_version(package),
                registry.get_path(package), registry.is_removable(package))


def run(argv):
    parser = OptionParser("%prog list [options]")
    parser.add_option(
        "--root", metavar="PATH", help="look for additional packages in PATH")
    parser.add_option(
        "--all", default=False, action="store_true",
        help="list all installed packages")
    parser.add_option(
        "--user", metavar="USER",
        help="list packages registered by USER (if you have permission)")
    parser.add_option(
        "--manifest", default=False, action="store_true",
        help="format output as a JSON array of manifests")
    options, _ = parser.parse_args(argv)
    json_output = []
    for package, version, path, writeable in list_packages(options):
        if options.manifest:
            try:
                manifest_path = os.path.join(
                    path, ".click", "info", "%s.manifest" % package)
                with io.open(manifest_path, encoding="UTF-8") as manifest:
                    manifest_json = json.load(manifest)
                    keys = list(manifest_json)
                    for key in keys:
                        if key.startswith("_"):
                            del manifest_json[key]
                    manifest_json["_directory"] = path
                    manifest_json["_removable"] = 1 if writeable else 0
                    json_output.append(manifest_json)
            except Exception:
                pass
        else:
            print("%s\t%s" % (package, version))
    if options.manifest:
        json.dump(
            json_output, sys.stdout, ensure_ascii=False, sort_keys=True,
            indent=4, separators=(",", ": "))
        print()
    return 0
