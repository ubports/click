#! /usr/bin/python

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

"""Unit tests for clickpackage.osextras."""

from __future__ import print_function

import os

from clickpackage import osextras
from clickpackage.tests.helpers import TestCase, touch


class TestOSExtras(TestCase):
    def setUp(self):
        super(TestOSExtras, self).setUp()
        self.use_temp_dir()

    def test_ensuredir_previously_missing(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        osextras.ensuredir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_ensuredir_previously_present(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        os.mkdir(new_dir)
        osextras.ensuredir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_find_on_path_missing_environment(self):
        os.environ.pop("PATH", None)
        self.assertFalse(osextras.find_on_path("ls"))

    def test_find_on_path_present_executable(self):
        bin_dir = os.path.join(self.temp_dir, "bin")
        program = os.path.join(bin_dir, "program")
        touch(program)
        os.chmod(program, 0o755)
        os.environ["PATH"] = bin_dir
        self.assertTrue(osextras.find_on_path("program"))

    def test_find_on_path_present_not_executable(self):
        bin_dir = os.path.join(self.temp_dir, "bin")
        touch(os.path.join(bin_dir, "program"))
        os.environ["PATH"] = bin_dir
        self.assertFalse(osextras.find_on_path("program"))
