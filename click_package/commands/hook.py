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

"""Install or remove a Click system hook."""

from __future__ import print_function

from optparse import OptionParser
import sys
from textwrap import dedent

from gi.repository import Click, GLib


per_hook_subcommands = {
    "install": "install",
    "remove": "remove",
    }


def run(argv):
    parser = OptionParser(dedent("""\
        %prog hook [options] SUBCOMMAND [...]

        Subcommands are as follows:

          install HOOK
          remove HOOK
          run-system
          run-user [--user=USER]"""))
    parser.add_option(
        "--root", metavar="PATH", help="look for additional packages in PATH")
    parser.add_option(
        "--user", metavar="USER",
        help=(
            "run user-level hooks for USER (default: current user; only "
            "applicable to run-user)"))
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need subcommand (install, remove, run-system, run-user)")
    subcommand = args[0]
    if subcommand in per_hook_subcommands:
        if len(args) < 2:
            parser.error("need hook name")
        db = Click.DB()
        db.read(db_dir=None)
        if options.root is not None:
            db.add(options.root)
        name = args[1]
        hook = Click.Hook.open(db, name)
        getattr(hook, per_hook_subcommands[subcommand])(user_name=None)
    elif subcommand == "run-system":
        db = Click.DB()
        db.read(db_dir=None)
        if options.root is not None:
            db.add(options.root)
        try:
            Click.run_system_hooks(db)
        except GLib.GError as e:
            if e.domain == "click_hooks_error-quark":
                print(e.message, file=sys.stderr)
                return 1
            else:
                raise
    elif subcommand == "run-user":
        db = Click.DB()
        db.read(db_dir=None)
        if options.root is not None:
            db.add(options.root)
        try:
            Click.run_user_hooks(db, user_name=options.user)
        except GLib.GError as e:
            if e.domain == "click_hooks_error-quark":
                print(e.message, file=sys.stderr)
                return 1
            else:
                raise
    else:
        parser.error(
            "unknown subcommand '%s' (known: install, remove, run-system,"
            "run-user)" % subcommand)
    return 0
