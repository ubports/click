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

"""Integration tests for the click CLI frameworks command."""

import os
import subprocess
import unittest

from .helpers import (
    ClickTestCase,
)


@unittest.skipIf(
    (not os.path.exists("/usr/share/click/frameworks") or
     not os.listdir("/usr/share/click/frameworks")),
    "Please install ubuntu-sdk-libs")
class TestFrameworks(ClickTestCase):
    def test_framework_list(self):
        output = subprocess.check_output([
            self.click_binary, "framework", "list"], universal_newlines=True)
        self.assertTrue("ubuntu-sdk-" in output)
