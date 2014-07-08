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

import subprocess

from .helpers import ClickTestCase


class TestVerify(ClickTestCase):
    def test_verify_ok(self):
        name = "com.ubuntu.verify-ok"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "verify", "--force-missing-framework",
            path_to_click], universal_newlines=True)
        self.assertEqual(output, "")
