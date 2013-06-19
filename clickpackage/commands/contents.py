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

"""Show the file-list contents of a Click package file."""

from __future__ import print_function

from optparse import OptionParser
import subprocess


def run(argv):
    parser = OptionParser("%prog contents [options] PATH")
    _, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need file name")
    path = args[0]
    subprocess.check_call(["dpkg-deb", "-c", path])
    return 0
