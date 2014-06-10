# Copyright (C) 2014 Canonical Ltd.
# Author: Michael Vogt <michael.vogt@ubuntu.com>

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

"""Integration tests for the click CLI interface."""

import copy
import contextlib
import glob
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest


@contextlib.contextmanager
def chdir(target):
    curdir = os.getcwd()
    os.chdir(target)
    yield
    os.chdir(curdir)


class TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.click_binary = os.path.abspath(
            os.path.join(sys.argv[0], "..", "bin", "click"))

    def setUp(self):
        self.saved_env = copy.copy(os.environ)
        os.environ["PYTHONPATH"] = os.path.abspath(
            os.path.join(sys.argv[0], ".."))

    def tearDown(self):
        os.environ = self.saved_env

    def _make_click(self, name=None, version=1.0):
        if name is None:
            name = "com.ubuntu.%s" % "".join(
                random.choice(string.ascii_lowercase) for i in range(10))
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir))
        clickdir = os.path.join(tmpdir, name)
        os.makedirs(clickdir)
        with open(os.path.join(clickdir, "manifest.json"), "w") as f:
            f.write("""{
            "name": "%s",
            "version": "%s",
            "maintainer": "Foo Bar <foo@example.org>",
            "title": "test title",
            "framework": "ubuntu-sdk-13.10"
            }""" % (name, version))
        with open(os.path.join(clickdir, "README"), "w") as f:
            f.write("hello world!")
        with chdir(tmpdir), open(os.devnull, "w") as devnull:
            subprocess.call(["click", "build", clickdir], stdout=devnull)
        generated_clicks = glob.glob(os.path.join(tmpdir, "*.click"))
        self.assertEqual(len(generated_clicks), 1)
        return generated_clicks[0]


class TestBuild(TestCase):
    def test_build(self):
        path_to_click = self._make_click()
        self.assertTrue(os.path.exists(path_to_click))


class TestInfo(TestCase):
    def test_info(self):
        name = "com.ubuntu.foo"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "info", path_to_click], universal_newlines=True)
        self.assertEqual(json.loads(output)["name"], name)


class TestVerify(TestCase):
    def test_verify_ok(self):
        name = "com.ubuntu.verify-ok"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "verify", "--force-missing-framework",
            path_to_click], universal_newlines=True)
        self.assertEqual(output, "")


class TestContents(TestCase):
    def test_contents(self):
        name = "com.ubuntu.contents"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "contents", path_to_click],
            universal_newlines=True)
        self.assertTrue(re.search(
            r'-rw-r[-w]-r-- root/root\s+[0-9]+\s+[0-9-]+ [0-9:]+ ./README', output))


@unittest.skipIf(
    os.getuid() != 0, "This tests needs to run as root")
@unittest.skipIf(
    subprocess.call(
        ["ping", "-c1", "archive.ubuntu.com"]) != 0, "Need network")
class TestChroot(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestChroot, cls).setUpClass()
        cls.arch = subprocess.check_output(
            ["dpkg", "--print-architecture"], universal_newlines=True).strip()
        subprocess.check_call([
            cls.click_binary,
            "chroot", "-a", cls.arch,
            "create"])

    @classmethod
    def tearDownClass(cls):
        subprocess.check_call([
            cls.click_binary,
            "chroot", "-a", cls.arch,
            "destroy"])

    def test_upgrade(self):
        subprocess.check_call([
            self.click_binary, "chroot", "-a", self.arch,
            "upgrade"])

    def test_install(self):
        subprocess.check_call([
            self.click_binary, "chroot", "-a", self.arch,
            "install", "apt-utils"])

    def test_run(self):
        output = subprocess.check_output([
            self.click_binary, "chroot", "-a", self.arch,
            "run", "echo", "hello world"], universal_newlines=True)
        self.assertEqual(output, "hello world\n")

    def test_maint(self):
        output = subprocess.check_output([
            self.click_binary, "chroot", "-a", self.arch,
            "maint", "id"], universal_newlines=True)
        self.assertEqual(output, "uid=0(root) gid=0(root) groups=0(root)\n")
