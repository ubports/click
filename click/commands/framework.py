# Copyright (C) 2014 Canonical Ltd.
# Author: Michael Vogt <mvo@ubuntu.com>

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

"""List available frameworks."""

from __future__ import print_function

from argparse import ArgumentParser

from gi.repository import Click


def list(parser, args):
    for framework in Click.Framework.get_frameworks():
        print("%s" % framework.props.name)
    return 0


def info(parser, args):
    framework = Click.Framework.open(args.framework_name)
    for field in sorted(framework.get_fields()):
        print("%s: %s" % (field, framework.get_field(field)))


def get_field(parser, args):
    framework = Click.Framework.open(args.framework_name)
    print(framework.get_field(args.field_name))


def run(argv):
    parser = ArgumentParser("click framework")
    subparsers = parser.add_subparsers()
    list_parser = subparsers.add_parser(
        "list",
        help="list available frameworks")
    list_parser.set_defaults(func=list)
    info_parser = subparsers.add_parser(
        "info",
        help="show info about a specific framework")
    info_parser.add_argument(
        "framework_name",
        help="framework name with the information")
    info_parser.set_defaults(func=info)
    get_field_parser = subparsers.add_parser(
        "get-field",
        help="get a field from a given framework")
    get_field_parser.add_argument(
        "framework_name",
        help="framework name with the information")
    get_field_parser.add_argument(
        "field_name",
        help="the field name (e.g. base-version)")
    get_field_parser.set_defaults(func=get_field)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(parser, args)
