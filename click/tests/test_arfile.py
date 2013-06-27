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

"""Unit tests for click.arfile."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestArFile',
    ]


import os
import subprocess

from click.arfile import ArFile
from click.tests.helpers import TestCase, touch


class TestArFile(TestCase):
    def setUp(self):
        super(TestArFile, self).setUp()
        self.use_temp_dir()

    def test_init_rejects_mode_r(self):
        self.assertRaises(ValueError, ArFile, mode="r")

    def test_init_name(self):
        path = os.path.join(self.temp_dir, "foo.a")
        with ArFile(name=path, mode="w") as arfile:
            self.assertEqual("w", arfile.mode)
            self.assertEqual("wb", arfile.real_mode)
            self.assertEqual(path, arfile.name)
            self.assertEqual(path, arfile.fileobj.name)
            self.assertTrue(arfile.opened_fileobj)
            self.assertFalse(arfile.closed)

    def test_init_rejects_readonly_fileobj(self):
        path = os.path.join(self.temp_dir, "foo.a")
        touch(path)
        with open(path, "rb") as fileobj:
            self.assertRaises(ValueError, ArFile, fileobj=fileobj)

    def test_init_fileobj(self):
        path = os.path.join(self.temp_dir, "foo.a")
        with open(path, "wb") as fileobj:
            arfile = ArFile(fileobj=fileobj)
            self.assertEqual("w", arfile.mode)
            self.assertEqual("wb", arfile.real_mode)
            self.assertEqual(path, arfile.name)
            self.assertEqual(fileobj, arfile.fileobj)
            self.assertFalse(arfile.opened_fileobj)
            self.assertFalse(arfile.closed)

    def test_writes_valid_ar_file(self):
        member_path = os.path.join(self.temp_dir, "member")
        with open(member_path, "wb") as member:
            member.write(b"\x00\x01\x02\x03\x04\x05\x06\x07")
        path = os.path.join(self.temp_dir, "foo.a")
        with ArFile(name=path, mode="w") as arfile:
            arfile.add_magic()
            arfile.add_data("data-member", b"some data")
            arfile.add_file("file-member", member_path)
        extract_path = os.path.join(self.temp_dir, "extract")
        os.mkdir(extract_path)
        subprocess.call(["ar", "x", path], cwd=extract_path)
        self.assertCountEqual(
            ["data-member", "file-member"], os.listdir(extract_path))
        with open(os.path.join(extract_path, "data-member"), "rb") as member:
            self.assertEqual(b"some data", member.read())
        with open(os.path.join(extract_path, "file-member"), "rb") as member:
            self.assertEqual(
                b"\x00\x01\x02\x03\x04\x05\x06\x07", member.read())
