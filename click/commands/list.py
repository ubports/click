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

from optparse import OptionParser
import os

from click.paths import default_root
from click.user import ClickUser


def list_packages(options):
    if options.all:
        for package in sorted(os.listdir(options.root)):
            if package == ".click":
                continue
            package_path = os.path.join(options.root, package)
            if not os.path.isdir(package_path):
                continue
            for version in sorted(os.listdir(package_path)):
                version_path = os.path.join(package_path, version)
                if (os.path.islink(version_path) or
                        not os.path.isdir(version_path)):
                    continue
                yield package, version
    else:
        registry = ClickUser(options.root, user=options.user)
        for package, version in sorted(registry.items()):
            yield package, version


def run(argv):
    parser = OptionParser("%prog list [options]")
    parser.add_option(
        "--root", metavar="PATH", default=default_root,
        help="set top-level directory to PATH (default: %s)" % default_root)
    parser.add_option(
        "--all", default=False, action="store_true",
        help="list all installed packages")
    parser.add_option(
        "--user", metavar="USER",
        help="list packages registered by USER (if you have permission)")
    options, _ = parser.parse_args()
    for package, version in list_packages(options):
        print("%s\t%s" % (package, version))
