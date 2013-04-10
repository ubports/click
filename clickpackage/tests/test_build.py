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

"""Unit tests for clickpackage.build."""

from __future__ import print_function

__metaclass__ = type

import os
import subprocess

from clickpackage.build import ClickBuilder
from clickpackage.preinst import static_preinst
from clickpackage.tests.helpers import TestCase, mkfile


class TestClickBuilder(TestCase):
    def make_builder(self, **kwargs):
        return ClickBuilder(
            "test", "1.0", "Foo Bar <foo@example.org>", "test description",
            **kwargs)

    def test_init(self):
        builder = self.make_builder()
        self.assertEqual("test", builder.name)
        self.assertEqual("1.0", builder.version)
        self.assertEqual("Foo Bar <foo@example.org>", builder.maintainer)
        self.assertEqual("test description", builder.description)
        self.assertEqual("all", builder.architecture)
        self.assertEqual({}, builder.file_map)

    def test_add_file(self):
        builder = self.make_builder()
        builder.add_file("/nonexistent", "target")
        self.assertEqual({"/nonexistent": "target"}, builder.file_map)

    def extract_field(self, path, name):
        return subprocess.check_output(
            ["dpkg-deb", "-f", path, name],
            universal_newlines=True).rstrip("\n")

    def extract_control_file(self, path, name):
        return subprocess.check_output(
            ["dpkg-deb", "-I", path, name], universal_newlines=True)

    def test_build(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        with mkfile(os.path.join(scratch, "bin", "foo")) as f:
            f.write("test /bin/foo\n")
        with mkfile(os.path.join(scratch, "toplevel")) as f:
            f.write("test /toplevel\n")
        builder = self.make_builder()
        builder.add_file(scratch, "/")
        path = os.path.join(self.temp_dir, "test_1.0_all.click")
        self.assertEqual(path, builder.build(self.temp_dir))
        self.assertTrue(os.path.exists(path))
        for key, value in (
            ("Package", "test"),
            ("Version", "1.0"),
            ("Click-Version", "0.1"),
            ("Click-Base-System", "13.04"),
            ("Architecture", "all"),
            ("Maintainer", "Foo Bar <foo@example.org>"),
            ("Description", "test description"),
        ):
            self.assertEqual(value, self.extract_field(path, key))
        self.assertNotEqual(
            "", self.extract_field(path, "Installed-Size"))
        self.assertEqual(
            "eb774c3ead632b397d6450d1df25e001  bin/foo\n"
            "49327ce6306df8a87522456b14a179e0  toplevel\n",
            self.extract_control_file(path, "md5sums"))
        self.assertEqual(
            static_preinst, self.extract_control_file(path, "preinst"))
        contents = subprocess.check_output(
            ["dpkg-deb", "-c", path], universal_newlines=True)
        self.assertRegex(contents, r"^drwxr-xr-x root/root         0 .* \./\n")
        self.assertRegex(
            contents, "\n-rw-r--r-- root/root        14 .* \./bin/foo\n")
        self.assertRegex(
            contents, "\n-rw-r--r-- root/root        15 .* \./toplevel\n")
        extract_path = os.path.join(self.temp_dir, "extract")
        subprocess.check_call(["dpkg-deb", "-x", path, extract_path])
        with open(os.path.join(extract_path, "bin", "foo")) as f:
            self.assertEqual("test /bin/foo\n", f.read())
        with open(os.path.join(extract_path, "toplevel")) as f:
            self.assertEqual("test /toplevel\n", f.read())
