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

"""Integration tests helper for the click CLI interface."""

import contextlib
import glob
import json
import os
import random
import shutil
import string
import subprocess
import tempfile
import unittest


def require_root():
    if os.getuid() != 0:
        raise unittest.SkipTest("This test needs to run as root")


def require_network():
    try:
        if subprocess.call(["ping", "-c1", "archive.ubuntu.com"]) != 0:
            raise unittest.SkipTest("Need network")
    except Exception:
        pass


@contextlib.contextmanager
def chdir(target):
    curdir = os.getcwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(curdir)


def cmdline_for_user(username):
    """Helper to get the click commandline for the given username"""
    if username == "@all":
        user = "--all-users"
    else:
        user = "--user=%s" % username
    return user


class ClickTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if "TEST_INTEGRATION" not in os.environ:
            raise unittest.SkipTest("Skipping integration tests")
        cls.click_binary = os.environ.get("CLICK_BINARY", "/usr/bin/click")

    def setUp(self):
        super(ClickTestCase, self).setUp()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super(ClickTestCase, self).tearDown()
        # we force the cleanup before removing the tempdir so that stuff
        # in temp_dir is still available
        self.doCleanups()
        shutil.rmtree(self.temp_dir)

    def click_install(self, path_to_click, click_name, username,
                      allow_unauthenticated=True):
        cmd = [self.click_binary, "install", cmdline_for_user(username)]
        if allow_unauthenticated:
            cmd.append("--allow-unauthenticated")
        cmd.append(path_to_click)
        subprocess.check_call(cmd)
        self.addCleanup(self.click_unregister, click_name, username)

    def click_unregister(self, click_name, username):
        subprocess.check_call(
            [self.click_binary, "unregister", cmdline_for_user(username),
             click_name])

    def _create_manifest(self, target, name, version, framework, hooks={}):
        with open(target, "w") as f:
            json.dump({
                'name': name,
                'version': str(version),
                'maintainer': 'Foo Bar <foo@example.org>',
                'title': 'test title',
                'framework': framework,
                'hooks': hooks,
                }, f)

    def _make_click(self, name=None, version=1.0,
                    framework="ubuntu-sdk-13.10", hooks={}):
        if name is None:
            name = "com.example.%s" % "".join(
                random.choice(string.ascii_lowercase) for i in range(10))
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir))
        clickdir = os.path.join(tmpdir, name)
        os.makedirs(clickdir)
        self._create_manifest(os.path.join(clickdir, "manifest.json"),
                              name, version, framework, hooks)
        with open(os.path.join(clickdir, "README"), "w") as f:
            f.write("hello world!")
        with chdir(tmpdir), open(os.devnull, "w") as devnull:
            subprocess.call(
                [self.click_binary, "build", clickdir], stdout=devnull)
        generated_clicks = glob.glob(os.path.join(tmpdir, "*.click"))
        self.assertEqual(len(generated_clicks), 1)
        return generated_clicks[0]
