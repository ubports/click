#! /usr/bin/python3

# Copyright (C) 2013 Canonical Ltd.
# Author: Brian Murray <brian@ubuntu.com>

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

"""Use and manage a Click chroot."""

from __future__ import print_function

from argparse import ArgumentParser, REMAINDER
import os

from click.chroot import ClickChroot
from click import osextras


def requires_root(parser):
    if os.getuid() != 0:
        parser.error("must be run as root; try sudo")


def create(parser, args):
    if not osextras.find_on_path("debootstrap"):
        parser.error(
            "debootstrap not installed and configured; install click-dev and "
            "debootstrap")
    requires_root(parser)
    ClickChroot(args.architecture, args.framework, series=args.series).create()


def install(parser, args):
    packages = args.packages
    ClickChroot(args.architecture, args.framework).install(*packages)


def destroy(parser, args):
    requires_root(parser)
    # ask for confirmation?
    ClickChroot(args.architecture, args.framework).destroy()


def execute(parser, args):
    program = args.program
    if not program:
        program = ["/bin/bash"]
    ClickChroot(args.architecture, args.framework, session=args.session).run(*program)


def maint(parser, args):
    program = args.program
    if not program:
        program = ["/bin/bash"]
    ClickChroot(args.architecture, args.framework, session=args.session).maint(*program)


def upgrade(parser, args):
    ClickChroot(args.architecture, args.framework).upgrade()


def begin_session(parser, args):
    ClickChroot(args.architecture, args.framework, session=args.session).begin_session()


def end_session(parser, args):
    ClickChroot(args.architecture, args.framework, session=args.session).end_session()


def run(argv):
    parser = ArgumentParser("click chroot")
    subparsers = parser.add_subparsers(
        description="management subcommands",
        help="valid commands")
    parser.add_argument(
        "-a", "--architecture", required=True,
        help="architecture for the chroot")
    parser.add_argument(
        "-f", "--framework", default="ubuntu-sdk-13.10",
        help="framework for the chroot (default: ubuntu-sdk-13.10)")
    parser.add_argument(
        "-s", "--series",
        help="series to use for a newly-created chroot (defaults to a series "
             "appropriate for the framework)")
    create_parser = subparsers.add_parser(
        "create",
        help="create a chroot of the provided architecture")
    create_parser.set_defaults(func=create)
    destroy_parser = subparsers.add_parser(
        "destroy",
        help="destroy the chroot")
    destroy_parser.set_defaults(func=destroy)
    upgrade_parser = subparsers.add_parser(
        "upgrade",
        help="upgrade the chroot")
    upgrade_parser.set_defaults(func=upgrade)
    install_parser = subparsers.add_parser(
        "install",
        help="install packages in the chroot")
    install_parser.add_argument(
        "packages", nargs="+",
        help="packages to install")
    install_parser.set_defaults(func=install)
    execute_parser = subparsers.add_parser(
        "run",
        help="run a program in the chroot")
    execute_parser.add_argument(
        "-n", "--session-name",
        dest='session',
        help="persistent chroot session name to run a program in")
    execute_parser.add_argument(
        "program", nargs=REMAINDER,
        help="program to run with arguments")
    execute_parser.set_defaults(func=execute)
    maint_parser = subparsers.add_parser(
        "maint",
        help="run a maintenance command in the chroot")
    maint_parser.add_argument(
        "-n", "--session-name",
        dest='session',
        help="persistent chroot session name to run a maintenance command in")
    maint_parser.add_argument(
        "program", nargs=REMAINDER,
        help="program to run with arguments")
    maint_parser.set_defaults(func=maint)
    begin_parser = subparsers.add_parser(
        "begin-session",
        help="begin a persistent chroot session")
    begin_parser.add_argument(
        "session",
        help="new session name")
    begin_parser.set_defaults(func=begin_session)
    end_parser = subparsers.add_parser(
        "end-session",
        help="end a persistent chroot session")
    end_parser.add_argument(
        "session",
        help="session name to end")
    end_parser.set_defaults(func=end_session)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    if (not osextras.find_on_path("schroot") or
            not os.path.exists("/etc/schroot/click/fstab")):
        parser.error(
            "schroot not installed and configured; install click-dev and "
            "schroot")
    args.func(parser, args)
    return 0
