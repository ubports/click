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

"""Register an installed Click package for a user."""

from __future__ import print_function

from optparse import OptionParser

from gi.repository import Click, GLib


def run(argv):
    parser = OptionParser("%prog register [options] PACKAGE-NAME VERSION")
    parser.add_option(
        "--root", metavar="PATH", help="look for additional packages in PATH")
    parser.add_option(
        "--user", metavar="USER",
        help="register package for USER (default: current user)")
    parser.add_option(
        "--all-users", default=False, action="store_true",
        help="register package for all users")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package name")
    if len(args) < 2:
        parser.error("need version")
    db = Click.DB()
    db.read()
    if options.root is not None:
        db.add(options.root)
    package = args[0]
    version = args[1]
    if options.all_users:
        registry = Click.User.for_all_users(db)
    else:
        registry = Click.User.for_user(db, name=options.user)
    try:
        old_version = registry.get_version(package)
    except GLib.GError:
        old_version = None
    registry.set_version(package, version)
    if old_version is not None:
        db.maybe_remove(package, old_version)
    return 0
