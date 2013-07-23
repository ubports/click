#! /usr/bin/python3

# Copyright (C) 2013 Canonical Ltd.

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

"""Print the directory where a Click package is unpacked."""

from __future__ import print_function

from optparse import OptionParser

from click.paths import default_root
from click.query import find_package_directory
from click.user import ClickUser


def run(argv):
    parser = OptionParser("%prog pkgdir {PACKAGE-NAME|PATH}")
    parser.add_option(
        "--root", metavar="PATH", default=default_root,
        help="set top-level directory to PATH (default: %s)" % default_root)
    parser.add_option(
        "--user", metavar="USER",
        help="look up PACKAGE-NAME for USER (if you have permission; "
             "default: current user)")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package name")
    if "/" in args[0]:
        print(find_package_directory(args[0]))
    else:
        package_name = args[0]
        registry = ClickUser(options.root, user=options.user)
        print(registry.path(package_name))
    return 0
