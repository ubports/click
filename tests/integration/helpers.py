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
import os
import random
import shutil
import string
import subprocess
import tempfile
import unittest


@contextlib.contextmanager
def chdir(target):
    curdir = os.getcwd()
    os.chdir(target)
    try:
        yield
    finally:
        os.chdir(curdir)


class TestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.click_binary = os.environ.get("CLICK_BINARY", "/usr/bin/click")

    def _create_manifest(self, target, name, version, framework):
        with open(target, "w") as f:
            f.write("""{
            "name": "%s",
            "version": "%s",
            "maintainer": "Foo Bar <foo@example.org>",
            "title": "test title",
            "framework": "%s"
            }""" % (name, version, framework))

    def _make_click(self, name=None, version=1.0, framework="ubuntu-sdk-13.10"):
        if name is None:
            name = "com.ubuntu.%s" % "".join(
                random.choice(string.ascii_lowercase) for i in range(10))
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir))
        clickdir = os.path.join(tmpdir, name)
        os.makedirs(clickdir)
        self._create_manifest(os.path.join(clickdir, "manifest.json"),
                              name, version, framework)
        with open(os.path.join(clickdir, "README"), "w") as f:
            f.write("hello world!")
        with chdir(tmpdir), open(os.devnull, "w") as devnull:
            subprocess.call(
                [self.click_binary, "build", clickdir], stdout=devnull)
        generated_clicks = glob.glob(os.path.join(tmpdir, "*.click"))
        self.assertEqual(len(generated_clicks), 1)
        return generated_clicks[0]
