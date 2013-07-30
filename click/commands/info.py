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

"""Show manifest information on a Click package file."""

from __future__ import print_function

from contextlib import closing
import json
from optparse import OptionParser

from click.install import DebFile


def run(argv):
    parser = OptionParser("%prog info [options] PATH")
    _, args = parser.parse_args(argv)
    if len(args) < 1:
        parser.error("need file name")
    path = args[0]
    with closing(DebFile(filename=path)) as package:
        with package.control.get_file(
                "manifest", encoding="UTF-8") as manifest:
            manifest_json = json.loads(manifest.read())
            print(json.dumps(
                manifest_json, ensure_ascii=False, sort_keys=True, indent=4,
                separators=(",", ": ")))
    return 0
