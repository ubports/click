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
from textwrap import dedent

from click.database import ClickDB
from click.install import ClickInstaller


def run(argv):
    parser = OptionParser(dedent("""\
        %prog install [options] PACKAGE-FILE

        This is a low-level tool; to install a package as an ordinary user
        you should generally use "pkcon install-local PACKAGE-FILE"
        instead."""))
    parser.add_option(
        "--root", metavar="PATH", help="install packages underneath PATH")
    parser.add_option(
        "--force-missing-framework", action="store_true", default=False,
        help="install despite missing system framework")
    parser.add_option(
        "--user", metavar="USER", help="register package for USER")
    parser.add_option(
        "--all-users", default=False, action="store_true",
        help="register package for all users")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package file name")
    db = ClickDB(options.root)
    package_path = args[0]
    installer = ClickInstaller(db, options.force_missing_framework)
    installer.install(
        package_path, user=options.user, all_users=options.all_users)
    return 0
