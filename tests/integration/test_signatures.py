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

"""Integration tests for the click signature checking."""

import os
import subprocess

from .helpers import ClickTestCase


class ClickSignaturesTestCase(ClickTestCase):
    def assertClickSignatureCheckError(self, cmd_args):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            output = subprocess.check_output(
                [self.click_binary] + cmd_args,
                stderr=subprocess.STDOUT, universal_newlines=True)
        output = cm.exception.output
        expected_error_message = (
            "Signature verification "
            "failed: debsig: Origin Signature check failed. This deb might "
            "not be signed.")
        self.assertIn(expected_error_message, output)


class TestSignatureVerification(ClickSignaturesTestCase):
    def test_debsig_verify_no_sig(self):
        name = "com.ubuntu.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        self.assertClickSignatureCheckError(["verify", path_to_click])

    def test_debsig_install_no_sig(self):
        name = "com.ubuntu.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        self.assertClickSignatureCheckError(["install", path_to_click])

    def test_debsig_install_can_install_with_sig_override(self):
        name = "com.ubuntu.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        user = os.environ.get("USER", "root")
        subprocess.check_call(
            [self.click_binary, "install",
             "--allow-unauthenticated", "--user=%s" % user,
             path_to_click])
        self.addCleanup(
            subprocess.call, [self.click_binary, "unregister",
                              "--user=%s" % user, name])
                        
