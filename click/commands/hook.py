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
from textwrap import dedent

from click.database import ClickDB
from click.hooks import ClickHook, run_user_hooks


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
          install-user [--user=USER]"""))
    parser.add_option(
        "--root", metavar="PATH", help="look for additional packages in PATH")
    parser.add_option(
        "--user", metavar="USER",
        help=(
            "run user-level hooks for USER (default: current user; only "
            "applicable to install-user)"))
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need subcommand (install, remove, install-user)")
    subcommand = args[0]
    if subcommand in per_hook_subcommands:
        if len(args) < 2:
            parser.error("need hook name")
        db = ClickDB(options.root)
        name = args[1]
        hook = ClickHook.open(db, name)
        getattr(hook, per_hook_subcommands[subcommand])()
    elif subcommand == "install-user":
        db = ClickDB(options.root)
        run_user_hooks(db, user=options.user)
    else:
        parser.error(
            "unknown subcommand '%s' (known: install, remove, install-all)" %
            subcommand)
    return 0
