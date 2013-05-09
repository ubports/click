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
__all__ = [
    'TestClickBuilder',
    ]


import json
import os
import stat
import subprocess
from textwrap import dedent

from clickpackage.build import ClickBuilder
from clickpackage.preinst import static_preinst
from clickpackage.tests.helpers import TestCase, mkfile, touch


# BAW 2013-04-15: Some tests require umask 022.  Use this decorator to
# temporarily tweak the process's umask.  The test -- or system -- should
# probably be made more robust instead.
def umask(force_umask):
    def decorator(func):
        def wrapper(*args, **kws):
            old_umask = os.umask(force_umask)
            try:
                return func(*args, **kws)
            finally:
                os.umask(old_umask)
        return wrapper
    return decorator


class TestClickBuilder(TestCase):
    def test_read_manifest(self):
        self.use_temp_dir()
        manifest_path = os.path.join(self.temp_dir, "manifest.json")
        with mkfile(manifest_path) as manifest:
            print(dedent("""\
                {
                    "name": "com.ubuntu.test",
                    "version": "1.0",
                    "maintainer": "Foo Bar <foo@example.org>",
                    "description": "test description"
                }"""), file=manifest)
        builder = ClickBuilder()
        builder.read_manifest(manifest_path)
        self.assertEqual("com.ubuntu.test", builder.name)
        self.assertEqual("1.0", builder.version)
        self.assertEqual("Foo Bar <foo@example.org>", builder.maintainer)
        self.assertEqual("test description", builder.description)
        self.assertEqual("all", builder.architecture)

    def test_add_file(self):
        builder = ClickBuilder()
        builder.add_file("/nonexistent", "target")
        self.assertEqual({"/nonexistent": "target"}, builder.file_map)

    def extract_field(self, path, name):
        return subprocess.check_output(
            ["dpkg-deb", "-f", path, name],
            universal_newlines=True).rstrip("\n")

    def extract_control_file(self, path, name):
        return subprocess.check_output(
            ["dpkg-deb", "-I", path, name], universal_newlines=True)

    @umask(0o22)
    def test_build(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        with mkfile(os.path.join(scratch, "bin", "foo")) as f:
            f.write("test /bin/foo\n")
        with mkfile(os.path.join(scratch, "toplevel")) as f:
            f.write("test /toplevel\n")
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            f.write(json.dumps({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "description": "test description",
                "architecture": "all",
            }))
            # build() overrides this back to 0o644
            os.fchmod(f.fileno(), 0o600)
        builder = ClickBuilder()
        builder.add_file(scratch, "/")
        path = os.path.join(self.temp_dir, "com.ubuntu.test_1.0_all.click")
        self.assertEqual(path, builder.build(self.temp_dir))
        self.assertTrue(os.path.exists(path))
        for key, value in (
            ("Package", "com.ubuntu.test"),
            ("Version", "1.0"),
            ("Click-Version", "0.1"),
            ("Click-Profile", "13.04"),
            ("Architecture", "all"),
            ("Maintainer", "Foo Bar <foo@example.org>"),
            ("Description", "test description"),
        ):
            self.assertEqual(value, self.extract_field(path, key))
        self.assertNotEqual(
            "", self.extract_field(path, "Installed-Size"))
        self.assertRegex(
            self.extract_control_file(path, "md5sums"),
            r"^"
            r"eb774c3ead632b397d6450d1df25e001  bin/foo\n"
            r".*  manifest.json\n"
            r"49327ce6306df8a87522456b14a179e0  toplevel\n"
            r"$")
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
        for rel_path in (
            os.path.join("bin", "foo"),
            "toplevel",
            "manifest.json",
        ):
            with open(os.path.join(scratch, rel_path)) as source, \
                    open(os.path.join(extract_path, rel_path)) as target:
                self.assertEqual(source.read(), target.read())
        manifest_path = os.path.join(extract_path, "manifest.json")
        self.assertEqual(0o644, stat.S_IMODE(os.stat(manifest_path).st_mode))

    def test_build_excludes_dot_click(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        touch(os.path.join(scratch, ".click", "evil-file"))
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            f.write(json.dumps({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "description": "test description",
                "architecture": "all",
            }))
        builder = ClickBuilder()
        builder.add_file(scratch, "/")
        path = builder.build(self.temp_dir)
        extract_path = os.path.join(self.temp_dir, "extract")
        subprocess.check_call(["dpkg-deb", "-x", path, extract_path])
        self.assertEqual(["manifest.json"], os.listdir(extract_path))
