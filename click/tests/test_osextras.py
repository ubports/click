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

"""Unit tests for click.osextras."""

from __future__ import print_function
__all__ = [
    'TestOSExtras',
    ]


import os

from click import osextras
from click.tests.helpers import TestCase, touch


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

    def test_listdir_directory_present(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        touch(os.path.join(new_dir, "file"))
        self.assertEqual(["file"], osextras.listdir_force(new_dir))

    def test_listdir_directory_missing(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        self.assertEqual([], osextras.listdir_force(new_dir))

    def test_listdir_oserror(self):
        not_dir = os.path.join(self.temp_dir, "file")
        touch(not_dir)
        self.assertRaises(OSError, osextras.listdir_force, not_dir)

    def test_unlink_file_present(self):
        path = os.path.join(self.temp_dir, "file")
        touch(path)
        osextras.unlink_force(path)
        self.assertFalse(os.path.exists(path))

    def test_unlink_file_missing(self):
        path = os.path.join(self.temp_dir, "file")
        osextras.unlink_force(path)
        self.assertFalse(os.path.exists(path))

    def test_unlink_oserror(self):
        path = os.path.join(self.temp_dir, "dir")
        os.mkdir(path)
        self.assertRaises(OSError, osextras.unlink_force, path)

    def test_symlink_file_present(self):
        path = os.path.join(self.temp_dir, "link")
        touch(path)
        osextras.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_symlink_link_present(self):
        path = os.path.join(self.temp_dir, "link")
        os.symlink("old", path)
        osextras.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_symlink_missing(self):
        path = os.path.join(self.temp_dir, "link")
        osextras.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_umask(self):
        old_mask = os.umask(0o040)
        try:
            self.assertEqual(0o040, osextras.get_umask())
            os.umask(0o002)
            self.assertEqual(0o002, osextras.get_umask())
        finally:
            os.umask(old_mask)
