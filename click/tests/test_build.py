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

"""Unit tests for click.build."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestClickBuilder',
    'TestClickSourceBuilder',
    ]


import json
import os
import stat
import subprocess
import tarfile
from textwrap import dedent

from click.build import ClickBuildError, ClickBuilder, ClickSourceBuilder
from click.preinst import static_preinst
from click.tests.helpers import TestCase, mkfile, touch


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


class TestClickBuilderBaseMixin:
    def test_read_manifest(self):
        self.use_temp_dir()
        manifest_path = os.path.join(self.temp_dir, "manifest.json")
        with mkfile(manifest_path) as manifest:
            print(dedent("""\
                {
                    "name": "com.ubuntu.test",
                    "version": "1.0",
                    "maintainer": "Foo Bar <foo@example.org>",
                    "title": "test title",
                    "framework": "ubuntu-sdk-13.10"
                }"""), file=manifest)
        self.builder.read_manifest(manifest_path)
        self.assertEqual("com.ubuntu.test", self.builder.name)
        self.assertEqual("1.0", self.builder.version)
        self.assertEqual("Foo Bar <foo@example.org>", self.builder.maintainer)
        self.assertEqual("test title", self.builder.title)
        self.assertEqual("all", self.builder.architecture)

    def test_add_file(self):
        self.builder.add_file("/nonexistent", "target")
        self.assertEqual({"/nonexistent": "target"}, self.builder.file_map)

    def test_epochless_version(self):
        self.use_temp_dir()
        manifest_path = os.path.join(self.temp_dir, "manifest.json")
        for version, epochless_version in (
            ("1.0", "1.0"),
            ("1:1.2.3", "1.2.3"),
        ):
            with mkfile(manifest_path) as manifest:
                print(dedent("""\
                    {
                        "name": "com.ubuntu.test",
                        "version": "%s",
                        "maintainer": "Foo Bar <foo@example.org>",
                        "title": "test title",
                        "framework": "ubuntu-sdk-13.10"
                    }""") % version, file=manifest)
            self.builder.read_manifest(manifest_path)
            self.assertEqual(epochless_version, self.builder.epochless_version)

    def test_manifest_syntax_error(self):
        self.use_temp_dir()
        manifest_path = os.path.join(self.temp_dir, "manifest.json")
        with mkfile(manifest_path) as manifest:
            # The comma after the "name" entry is intentionally missing.
            print(dedent("""\
                {
                    "name": "com.ubuntu.test"
                    "version": "1.0"
                }"""), file=manifest)
        self.assertRaises(
            ClickBuildError, self.builder.read_manifest, manifest_path)


class TestClickBuilder(TestCase, TestClickBuilderBaseMixin):
    def setUp(self):
        super(TestClickBuilder, self).setUp()
        self.builder = ClickBuilder()

    def extract_field(self, path, name):
        return subprocess.check_output(
            ["dpkg-deb", "-f", path, name],
            universal_newlines=True).rstrip("\n")

    @umask(0o22)
    def test_build(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        with mkfile(os.path.join(scratch, "bin", "foo")) as f:
            f.write("test /bin/foo\n")
        os.symlink("foo", os.path.join(scratch, "bin", "bar"))
        touch(os.path.join(scratch, ".git", "config"))
        with mkfile(os.path.join(scratch, "toplevel")) as f:
            f.write("test /toplevel\n")
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            json.dump({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "title": "test title",
                "architecture": "all",
                "framework": "ubuntu-sdk-13.10",
            }, f)
            # build() overrides this back to 0o644
            os.fchmod(f.fileno(), 0o600)
        self.builder.add_file(scratch, "/")
        path = os.path.join(self.temp_dir, "com.ubuntu.test_1.0_all.click")
        self.assertEqual(path, self.builder.build(self.temp_dir))
        self.assertTrue(os.path.exists(path))
        for key, value in (
            ("Package", "com.ubuntu.test"),
            ("Version", "1.0"),
            ("Click-Version", "0.4"),
            ("Architecture", "all"),
            ("Maintainer", "Foo Bar <foo@example.org>"),
            ("Description", "test title"),
        ):
            self.assertEqual(value, self.extract_field(path, key))
        self.assertNotEqual(
            "", self.extract_field(path, "Installed-Size"))
        control_path = os.path.join(self.temp_dir, "control")
        subprocess.check_call(["dpkg-deb", "-e", path, control_path])
        manifest_path = os.path.join(control_path, "manifest")
        self.assertEqual(0o644, stat.S_IMODE(os.stat(manifest_path).st_mode))
        with open(os.path.join(scratch, "manifest.json")) as source, \
                open(manifest_path) as target:
            source_json = json.load(source)
            target_json = json.load(target)
            self.assertNotEqual("", target_json["installed-size"])
            del target_json["installed-size"]
            self.assertEqual(source_json, target_json)
        with open(os.path.join(control_path, "md5sums")) as md5sums:
            self.assertRegex(
                md5sums.read(),
                r"^"
                r"eb774c3ead632b397d6450d1df25e001  bin/bar\n"
                r"eb774c3ead632b397d6450d1df25e001  bin/foo\n"
                r"49327ce6306df8a87522456b14a179e0  toplevel\n"
                r"$")
        with open(os.path.join(control_path, "preinst")) as preinst:
            self.assertEqual(static_preinst, preinst.read())
        contents = subprocess.check_output(
            ["dpkg-deb", "-c", path], universal_newlines=True)
        self.assertRegex(contents, r"^drwxr-xr-x root/root         0 .* \./\n")
        self.assertRegex(
            contents,
            "\nlrwxrwxrwx root/root         0 .* \./bin/bar -> foo\n")
        self.assertRegex(
            contents, "\n-rw-r--r-- root/root        14 .* \./bin/foo\n")
        self.assertRegex(
            contents, "\n-rw-r--r-- root/root        15 .* \./toplevel\n")
        extract_path = os.path.join(self.temp_dir, "extract")
        subprocess.check_call(["dpkg-deb", "-x", path, extract_path])
        for rel_path in (
            os.path.join("bin", "foo"),
            "toplevel",
        ):
            with open(os.path.join(scratch, rel_path)) as source, \
                    open(os.path.join(extract_path, rel_path)) as target:
                self.assertEqual(source.read(), target.read())
        self.assertTrue(
            os.path.islink(os.path.join(extract_path, "bin", "bar")))
        self.assertEqual(
            "foo", os.readlink(os.path.join(extract_path, "bin", "bar")))

    def test_build_excludes_dot_click(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        touch(os.path.join(scratch, ".click", "evil-file"))
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            json.dump({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "title": "test title",
                "architecture": "all",
                "framework": "ubuntu-sdk-13.10",
            }, f)
        self.builder.add_file(scratch, "/")
        path = self.builder.build(self.temp_dir)
        extract_path = os.path.join(self.temp_dir, "extract")
        subprocess.check_call(["dpkg-deb", "-x", path, extract_path])
        self.assertEqual([], os.listdir(extract_path))

    def test_build_multiple_architectures(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            json.dump({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "title": "test title",
                "architecture": ["armhf", "i386"],
                "framework": "ubuntu-sdk-13.10",
            }, f)
        self.builder.add_file(scratch, "/")
        path = os.path.join(self.temp_dir, "com.ubuntu.test_1.0_multi.click")
        self.assertEqual(path, self.builder.build(self.temp_dir))
        self.assertTrue(os.path.exists(path))
        self.assertEqual("multi", self.extract_field(path, "Architecture"))
        control_path = os.path.join(self.temp_dir, "control")
        subprocess.check_call(["dpkg-deb", "-e", path, control_path])
        manifest_path = os.path.join(control_path, "manifest")
        with open(os.path.join(scratch, "manifest.json")) as source, \
                open(manifest_path) as target:
            source_json = json.load(source)
            target_json = json.load(target)
            del target_json["installed-size"]
            self.assertEqual(source_json, target_json)

    def test_build_multiple_frameworks(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            json.dump({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "title": "test title",
                "architecture": "all",
                "framework":
                    "ubuntu-sdk-14.04-basic, ubuntu-sdk-14.04-webapps",
            }, f)
        self.builder.add_file(scratch, "/")
        self.assertRaisesRegex(
            ClickBuildError,
            'Multiple dependencies in framework "ubuntu-sdk-14.04-basic, '
            'ubuntu-sdk-14.04-webapps" not yet allowed',
            self.builder.build, self.temp_dir)


class TestClickSourceBuilder(TestCase, TestClickBuilderBaseMixin):
    def setUp(self):
        super(TestClickSourceBuilder, self).setUp()
        self.builder = ClickSourceBuilder()

    @umask(0o22)
    def test_build(self):
        self.use_temp_dir()
        scratch = os.path.join(self.temp_dir, "scratch")
        touch(os.path.join(scratch, "bin", "foo"))
        touch(os.path.join(scratch, ".git", "config"))
        with mkfile(os.path.join(scratch, "manifest.json")) as f:
            json.dump({
                "name": "com.ubuntu.test",
                "version": "1.0",
                "maintainer": "Foo Bar <foo@example.org>",
                "title": "test title",
                "architecture": "all",
                "framework": "ubuntu-sdk-13.10",
            }, f)
            # build() overrides this back to 0o644
            os.fchmod(f.fileno(), 0o600)
        self.builder.add_file(scratch, "./")
        path = os.path.join(self.temp_dir, "com.ubuntu.test_1.0.tar.gz")
        self.assertEqual(path, self.builder.build(self.temp_dir))
        self.assertTrue(os.path.exists(path))
        with tarfile.open(path, mode="r:gz") as tar:
            self.assertCountEqual(
                [".", "./bin", "./bin/foo", "./manifest.json"], tar.getnames())
            self.assertTrue(tar.getmember("./bin/foo").isfile())
