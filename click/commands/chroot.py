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
from contextlib import contextmanager
import os

from click.chroot import (
    ClickChroot,
    ClickChrootAlreadyExistsException,
    ClickChrootDoesNotExistException,
)
from click import osextras


def requires_root(parser):
    if os.getuid() != 0:
        parser.error("must be run as root; try sudo")


@contextmanager
def message_on_error(exc, msg):
    """
    Context Manager that prints the error message 'msg' on exception 'exc'
    """
    try:
        yield
    except exc:
        print(msg)


# FIXME: i18n(?)
class ErrorMessages:
    EXISTS = """A chroot for that name and architecture already exists.
Please see the man-page how to use it."""
    NOT_EXISTS = """A chroot for that name and architecture does not exist.
Please use 'create' to create it."""


def create(parser, args):
    if not osextras.find_on_path("debootstrap"):
        parser.error(
            "debootstrap not installed and configured; install click-dev and "
            "debootstrap")
    requires_root(parser)
    chroot = ClickChroot(args.architecture, args.framework, series=args.series)
    with message_on_error(
            ClickChrootAlreadyExistsException, ErrorMessages.EXISTS):
        return chroot.create(args.keep_broken_chroot)
    # if we reach this point there was a error so return exit_status 1
    return 1


def install(parser, args):
    packages = args.packages
    chroot = ClickChroot(args.architecture, args.framework)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.install(*packages)
    # if we reach this point there was a error so return exit_status 1
    return 1


def destroy(parser, args):
    requires_root(parser)
    # ask for confirmation?
    chroot = ClickChroot(args.architecture, args.framework)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.destroy()
    # if we reach this point there was a error so return exit_status 1
    return 1


def execute(parser, args):
    program = args.program
    if not program:
        program = ["/bin/bash"]
    chroot = ClickChroot(
        args.architecture, args.framework, session=args.session)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.run(*program)
    # if we reach this point there was a error so return exit_status 1
    return 1


def maint(parser, args):
    program = args.program
    if not program:
        program = ["/bin/bash"]
    chroot = ClickChroot(
        args.architecture, args.framework, session=args.session)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.maint(*program)
    # if we reach this point there was a error so return exit_status 1
    return 1


def upgrade(parser, args):
    chroot = ClickChroot(args.architecture, args.framework)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.upgrade()
    # if we reach this point there was a error so return exit_status 1
    return 1


def begin_session(parser, args):
    chroot = ClickChroot(
        args.architecture, args.framework, session=args.session)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.begin_session()
    # if we reach this point there was a error so return exit_status 1
    return 1


def end_session(parser, args):
    chroot = ClickChroot(
        args.architecture, args.framework, session=args.session)
    with message_on_error(
            ClickChrootDoesNotExistException, ErrorMessages.NOT_EXISTS):
        return chroot.end_session()
    # if we reach this point there was a error so return exit_status 1
    return 1


def exists(parser, args):
    chroot = ClickChroot(args.architecture, args.framework)
    # return shell exit codes 0 on success, 1 on failure
    if chroot.exists():
        return 0
    else:
        return 1


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
    create_parser.add_argument(
        "-k", "--keep-broken-chroot", default=False, action="store_true",
        help="Keep the chroot even if creating it fails (default is to delete "
              "it)")
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
    exists_parser = subparsers.add_parser(
        "exists",
        help="test if the given chroot exists")
    exists_parser.set_defaults(func=exists)
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    if (not osextras.find_on_path("schroot") or
            not os.path.exists("/etc/schroot/click/fstab")):
        parser.error(
            "schroot not installed and configured; install click-dev and "
            "schroot")
    return args.func(parser, args)
