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

"""Find an installed Click package version for the user."""

from __future__ import print_function

from optparse import OptionParser
import os

from click.paths import default_root


def run(argv):
    parser = OptionParser("%prog pkgdir PACKAGE-NAME")
    parser.add_option(
        "--root", metavar="PATH", default=default_root,
        help="set top-level directory to PATH (default: %s)" % default_root)
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package name")
    package_name = args[0]
    print(os.path.join(options.root, package_name, "current"))
    return 0
