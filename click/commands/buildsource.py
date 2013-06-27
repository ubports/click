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

"""Build a Click source package."""

from __future__ import print_function

from optparse import OptionParser

from click.build import ClickSourceBuilder


def run(argv):
    parser = OptionParser("%prog buildsource [options] DIRECTORY")
    parser.add_option(
        "-m", "--manifest", metavar="PATH",
        help="read package manifest from PATH")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need directory")
    directory = args[0]
    builder = ClickSourceBuilder()
    builder.add_file(directory, "./")
    path = builder.build(".", manifest_path=options.manifest)
    print("Successfully built source package in '%s'." % path)
    return 0
