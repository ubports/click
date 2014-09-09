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

"""Integration tests for the click CLI contents command."""

import re
import subprocess

from .helpers import ClickTestCase


class TestContents(ClickTestCase):
    def test_contents(self):
        name = "com.example.contents"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "contents", path_to_click],
            universal_newlines=True)
        self.assertTrue(re.search(
            r'-rw-r[-w]-r-- root/root\s+[0-9]+\s+[0-9-]+ [0-9:]+ ./README',
            output))
