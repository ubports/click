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

"""Integration tests for the click CLI buildsource command."""

import os
import shutil
import subprocess
import tarfile
import tempfile

from .helpers import (
    chdir,
    ClickTestCase,
)


class TestBuildSource(ClickTestCase):

    def test_buildsource(self):
        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir)
        with chdir(temp_dir):
            with open(os.path.join(temp_dir, "README"), "w") as f:
                f.write("I'm a source package")
            os.mkdir(os.path.join(temp_dir, ".git"))
            os.mkdir(os.path.join(temp_dir, ".bzr"))
            os.mkdir(os.path.join(temp_dir, ".normal"))
            self._create_manifest(os.path.join(temp_dir, "manifest.json"),
                                  "srcfoo", "1.2", "ubuntu-sdk-13.10")
            subprocess.check_call(
                [self.click_binary, "buildsource", temp_dir],
                universal_newlines=True)
            # ensure we have the content we expect
            source_file = "srcfoo_1.2.tar.gz"
            tar = tarfile.open(source_file)
            self.assertEqual(
                sorted(tar.getnames()),
                sorted([".", "./.normal", "./manifest.json", "./README"]))
