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

from optparse import OptionParser

from gi.repository import Click


def list_frameworks(options):
    all_frameworks = Click.Framework.get_frameworks()
    return all_frameworks


def run(argv):
    parser = OptionParser("%prog list-frameworks [options]")
    options, _ = parser.parse_args(argv)
    for framework in list_frameworks(options):
        print("%s" % framework.props.name)
    return 0
