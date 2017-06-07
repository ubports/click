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

"""Integration tests for the click CLI verify command."""

import os
import subprocess

from .helpers import ClickTestCase


class TestVerify(ClickTestCase):
    def test_verify_force_missing_framework_ok(self):
        name = "com.example.verify-missing-framework"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "verify",
            "--force-missing-framework",
            "--allow-unauthenticated",
            path_to_click], universal_newlines=True)
        self.assertEqual(output, "")

    def test_verify_force_ok(self):
        name = "com.example.verify-ok"
        path_to_click = self._make_click(name, framework="")
        output = subprocess.check_output([
            self.click_binary, "verify", "--allow-unauthenticated",
            path_to_click], universal_newlines=True)
        self.assertEqual(output, "")

    def test_verify_missing_framework(self):
        name = "com.example.verify-really-missing-framework"
        path_to_click = self._make_click(name, framework="missing")
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output(
                [self.click_binary, "verify",
                 "--allow-unauthenticated",
                 path_to_click],
                universal_newlines=True, stderr=subprocess.STDOUT)
        expected_error = (
            'click_package.framework.ClickFrameworkInvalid: Framework '
            '"missing" not present on system (use '
            '--force-missing-framework option to override)')
        self.assertIn(expected_error, cm.exception.output)

    def test_verify_no_click_but_invalid(self):
        name = "com.example.verify-no-click"
        path_to_click = os.path.join(self.temp_dir, name+".click")
        with open(path_to_click, "w") as f:
            f.write("something-that-is-not-a-click")
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            subprocess.check_output(
                [self.click_binary, "verify", "--allow-unauthenticated",
                 path_to_click],
                universal_newlines=True, stderr=subprocess.STDOUT)
        expected_error = (
            'click_package.install.DebsigVerifyError: '
            'Signature verification error: '
            'debsig: %s does not appear to be a deb format package'
        ) % path_to_click
        self.assertIn(expected_error, cm.exception.output)
