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

"""Install a Click package."""

from __future__ import print_function

from optparse import OptionParser

from click.install import ClickInstaller


# TODO: make configurable in build system or configuration file or similar?
default_root = "/opt/click.ubuntu.com"


def run(argv):
    parser = OptionParser("%prog install [options] PACKAGE-FILE")
    parser.add_option(
        "--root", metavar="PATH", default=default_root,
        help="set top-level directory to PATH (default: %s)" % default_root)
    parser.add_option(
        "--force-missing-framework", action="store_true", default=False,
        help="install despite missing system framework")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package file name")
    package_path = args[0]
    installer = ClickInstaller(options.root, options.force_missing_framework)
    installer.install(package_path)
    return 0
