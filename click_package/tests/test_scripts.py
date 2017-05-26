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

"""Test that all top-level scripts work."""

__metaclass__ = type
__all__ = [
    'TestScripts',
    ]

import os
import subprocess
from unittest import skipIf

from click_package.tests.helpers import TestCase


class TestScripts(TestCase):
    @skipIf('SKIP_SLOW_TESTS' in os.environ, 'Skipping slow tests')
    def test_scripts(self):
        self.longMessage = True
        paths = []
        for dirpath, _, filenames in os.walk("bin"):
            filenames = [
                n for n in filenames
                if not n.startswith(".") and not n.endswith("~")]
            for filename in filenames:
                paths.append(os.path.join(dirpath, filename))
        for path in paths:
            subp = subprocess.Popen(
                [path, "--help"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True)
            err = subp.communicate()[1]
            self.assertEqual("", err, "%s --help produced error output" % path)
            self.assertEqual(
                0, subp.returncode, "%s --help exited non-zero" % path)
