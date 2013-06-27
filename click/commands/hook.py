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

from click.hooks import ClickHook


# TODO: make configurable in build system or configuration file or similar?
default_root = "/opt/click.ubuntu.com"


subcommands = {
    "install": "install_all",
    "remove": "remove_all",
    }


def run(argv):
    parser = OptionParser("%prog hook [options] {install|remove} HOOK")
    parser.add_option(
        "--root", metavar="PATH", default=default_root,
        help="set top-level directory to PATH (default: %s)" % default_root)
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need subcommand (install, remove)")
    subcommand = args[0]
    if subcommand not in subcommands:
        parser.error(
            "unknown subcommand '%s' (known: install, remove)" % subcommand)
    if len(args) < 2:
        parser.error("need hook name")
    name = args[1]
    hook = ClickHook.open(name)
    getattr(hook, subcommands[subcommand])(options.root)
    return 0
