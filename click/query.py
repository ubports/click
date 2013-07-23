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

"""Query information about installed Click packages."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'find_package_directory',
    ]

import os


def _walk_up(path):
    while True:
        yield path
        newpath = os.path.dirname(path)
        if newpath == path:
            return
        path = newpath


def find_package_directory(path):
    for directory in _walk_up(os.path.realpath(path)):
        if os.path.isdir(os.path.join(directory, ".click", "info")):
            return directory
            break
    else:
        raise Exception("No package directory found for %s" % path)
