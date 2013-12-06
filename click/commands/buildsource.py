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
import os
import sys

from click.build import ClickBuildError, ClickSourceBuilder


def run(argv):
    parser = OptionParser("%prog buildsource [options] DIRECTORY")
    parser.add_option(
        "-m", "--manifest", metavar="PATH",
        help="read package manifest from PATH")
    options, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need directory")
    directory = args[0]
    if not os.path.isdir(directory):
        parser.error('directory "%s" does not exist' % directory)
    if os.path.isdir(os.path.join(directory, options.manifest)):
        options.manifest = os.path.join(options.manifest, "manifest.json")
    if not os.path.exists(os.path.join(directory, options.manifest)):
        parser.error(
            'directory "%s" does not contain manifest file "%s"' %
            (directory, options.manifest))
    builder = ClickSourceBuilder()
    builder.add_file(directory, "./")
    try:
        path = builder.build(".", manifest_path=options.manifest)
    except ClickBuildError as e:
        print(e, file=sys.stderr)
        return 1
    print("Successfully built source package in '%s'." % path)
    return 0
