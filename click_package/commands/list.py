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

import json
from optparse import OptionParser
import sys

from gi.repository import Click

from click_package.json_helpers import json_array_to_python


def list_packages(options):
    db = Click.DB()
    db.read(db_dir=None)
    if options.root is not None:
        db.add(options.root)
    if options.all:
        return json_array_to_python(db.get_manifests(all_versions=True))
    else:
        registry = Click.User.for_user(db, name=options.user)
        return json_array_to_python(registry.get_manifests())


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
    json_output = list_packages(options)
    if options.manifest:
        json.dump(
            json_output, sys.stdout, ensure_ascii=False, sort_keys=True,
            indent=4, separators=(",", ": "))
        print()
    else:
        for manifest in json_output:
            print("%s\t%s" % (manifest["name"], manifest["version"]))
    return 0
