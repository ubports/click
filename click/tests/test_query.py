# Copyright (C) 2014 Canonical Ltd.
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

"""Unit tests for click.query."""

from __future__ import print_function
__all__ = [
    'TestQuery',
    ]


import os

from gi.repository import Click

from click.tests.helpers import TestCase, touch


class TestQuery(TestCase):
    def setUp(self):
        super(TestQuery, self).setUp()
        self.use_temp_dir()

    def test_find_package_directory_missing(self):
        path = os.path.join(self.temp_dir, "nonexistent")
        self.assertRaisesQueryError(
            Click.QueryError.PATH, Click.find_package_directory, path)

    def test_find_package_directory(self):
        info = os.path.join(self.temp_dir, ".click", "info")
        path = os.path.join(self.temp_dir, "file")
        Click.ensuredir(info)
        touch(path)
        pkgdir = Click.find_package_directory(path)
        self.assertEqual(self.temp_dir, pkgdir)

    def test_find_package_directory_outside(self):
        self.assertRaisesQueryError(
            Click.QueryError.NO_PACKAGE_DIR, Click.find_package_directory,
            "/bin")
