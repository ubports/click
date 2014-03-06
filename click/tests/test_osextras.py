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
    'TestOSExtrasNative',
    'TestOSExtrasPython',
    ]


import os

from gi.repository import Click, GLib

from click import osextras
from click.tests.helpers import TestCase, mock, touch


class TestOSExtrasBaseMixin:
    def test_ensuredir_previously_missing(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        self.mod.ensuredir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_ensuredir_previously_present(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        os.mkdir(new_dir)
        self.mod.ensuredir(new_dir)
        self.assertTrue(os.path.isdir(new_dir))

    def test_find_on_path_missing_environment(self):
        os.environ.pop("PATH", None)
        self.assertFalse(self.mod.find_on_path("ls"))

    def test_find_on_path_present_executable(self):
        bin_dir = os.path.join(self.temp_dir, "bin")
        program = os.path.join(bin_dir, "program")
        touch(program)
        os.chmod(program, 0o755)
        os.environ["PATH"] = bin_dir
        self.assertTrue(self.mod.find_on_path("program"))

    def test_find_on_path_present_not_executable(self):
        bin_dir = os.path.join(self.temp_dir, "bin")
        touch(os.path.join(bin_dir, "program"))
        os.environ["PATH"] = bin_dir
        self.assertFalse(self.mod.find_on_path("program"))

    def test_find_on_path_requires_regular_file(self):
        bin_dir = os.path.join(self.temp_dir, "bin")
        self.mod.ensuredir(os.path.join(bin_dir, "subdir"))
        os.environ["PATH"] = bin_dir
        self.assertFalse(self.mod.find_on_path("subdir"))

    def test_unlink_file_present(self):
        path = os.path.join(self.temp_dir, "file")
        touch(path)
        self.mod.unlink_force(path)
        self.assertFalse(os.path.exists(path))

    def test_unlink_file_missing(self):
        path = os.path.join(self.temp_dir, "file")
        self.mod.unlink_force(path)
        self.assertFalse(os.path.exists(path))

    def test_symlink_file_present(self):
        path = os.path.join(self.temp_dir, "link")
        touch(path)
        self.mod.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_symlink_link_present(self):
        path = os.path.join(self.temp_dir, "link")
        os.symlink("old", path)
        self.mod.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_symlink_missing(self):
        path = os.path.join(self.temp_dir, "link")
        self.mod.symlink_force("source", path)
        self.assertTrue(os.path.islink(path))
        self.assertEqual("source", os.readlink(path))

    def test_umask(self):
        old_mask = os.umask(0o040)
        try:
            self.assertEqual(0o040, self.mod.get_umask())
            os.umask(0o002)
            self.assertEqual(0o002, self.mod.get_umask())
        finally:
            os.umask(old_mask)


class TestOSExtrasNative(TestCase, TestOSExtrasBaseMixin):
    def setUp(self):
        super(TestOSExtrasNative, self).setUp()
        self.use_temp_dir()
        self.mod = Click

    def test_dir_read_name_directory_present(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        touch(os.path.join(new_dir, "file"))
        d = Click.Dir.open(new_dir, 0)
        self.assertEqual("file", d.read_name())
        self.assertIsNone(d.read_name())

    def test_dir_read_name_directory_missing(self):
        new_dir = os.path.join(self.temp_dir, "dir")
        d = Click.Dir.open(new_dir, 0)
        self.assertIsNone(d.read_name())

    def test_dir_open_error(self):
        not_dir = os.path.join(self.temp_dir, "file")
        touch(not_dir)
        self.assertRaisesFileError(
            GLib.FileError.NOTDIR, Click.Dir.open, not_dir, 0)

    def test_unlink_error(self):
        path = os.path.join(self.temp_dir, "dir")
        os.mkdir(path)
        self.assertRaisesFileError(mock.ANY, self.mod.unlink_force, path)


class TestOSExtrasPython(TestCase, TestOSExtrasBaseMixin):
    def setUp(self):
        super(TestOSExtrasPython, self).setUp()
        self.use_temp_dir()
        self.mod = osextras

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

    def test_unlink_oserror(self):
        path = os.path.join(self.temp_dir, "dir")
        os.mkdir(path)
        self.assertRaises(OSError, self.mod.unlink_force, path)
