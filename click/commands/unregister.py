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

"""Unregister an installed Click package for a user."""

from __future__ import print_function

from optparse import OptionParser
import os
import sys

from gi.repository import Click


def run(argv):
    parser = OptionParser("%prog unregister [options] PACKAGE-NAME [VERSION]")
    parser.add_option(
        "--root", metavar="PATH", help="look for additional packages in PATH")
    parser.add_option(
        "--user", metavar="USER",
        help="unregister package for USER (default: $SUDO_USER, if known)")
    parser.add_option(
        "--all-users", default=False, action="store_true",
        help="unregister package that was previously registered for all users")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need package name")
    if os.geteuid() != 0:
        parser.error(
            "click unregister must be started as root, since it may need to "
            "remove packages from disk")
    if options.user is None and "SUDO_USER" in os.environ:
        options.user = os.environ["SUDO_USER"]
    db = Click.DB()
    db.read(db_dir=None)
    if options.root is not None:
        db.add(options.root)
    package = args[0]
    if options.all_users:
        registry = Click.User.for_all_users(db)
    else:
        registry = Click.User.for_user(db, name=options.user)
    old_version = registry.get_version(package)
    if len(args) >= 2 and old_version != args[1]:
        print(
            "Not removing %s %s; expected version %s" %
            (package, old_version, args[1]),
            file=sys.stderr)
        sys.exit(1)
    registry.remove(package)
    db.maybe_remove(package, old_version)
    # TODO: remove data
    return 0
