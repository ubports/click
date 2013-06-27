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

"""Preinst for Click packages.

In general there is a rule that Click packages may not have maintainer
scripts.  However, there is one exception: a static preinst used to cause
dpkg to fail if people attempt to install Click packages directly using dpkg
rather than via "click install".  This avoids accidents, since Click
packages use a different root of their filesystem tarball.
"""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'static_preinst',
    'static_preinst_matches',
    ]


_older_static_preinst = """\
#! /bin/sh
echo "Click packages may not be installed directly using dpkg."
echo "Use click-install instead."
exit 1
"""


_old_static_preinst = """\
#! /bin/sh
echo "Click packages may not be installed directly using dpkg."
echo "Use 'click-package install' instead."
exit 1
"""


static_preinst = """\
#! /bin/sh
echo "Click packages may not be installed directly using dpkg."
echo "Use 'click install' instead."
exit 1
"""


def static_preinst_matches(preinst):
    for allow_preinst in (
            _older_static_preinst,
            _old_static_preinst,
            static_preinst,
            ):
        if preinst == allow_preinst.encode():
            return True
    return False
