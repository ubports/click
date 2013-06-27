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

"""Test compliance with various static analysis tools."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestStatic',
    ]


import os
import sys
from unittest import skipIf

from pkg_resources import resource_filename

try:
    import pep8
except ImportError:
    pep8 = None
try:
    import pyflakes
    import pyflakes.api
    import pyflakes.reporter
except ImportError:
    pyflakes = None


from click.tests.helpers import TestCase


class TestStatic(TestCase):
    def all_paths(self):
        paths = []
        start_dir = os.path.dirname(resource_filename('click', '__init__.py'))
        for dirpath, dirnames, filenames in os.walk(start_dir):
            for ignore in ('doc', ".bzr", "__pycache__"):
                if ignore in dirnames:
                    dirnames.remove(ignore)
            filenames = [
                n for n in filenames
                if not n.startswith(".") and not n.endswith("~")]
            if dirpath.split(os.sep)[-1] == "bin":
                for filename in filenames:
                    paths.append(os.path.join(dirpath, filename))
            else:
                for filename in filenames:
                    if filename.endswith(".py"):
                        paths.append(os.path.join(dirpath, filename))
        return paths

    @skipIf('SKIP_SLOW_TESTS' in os.environ, 'Skipping slow tests')
    @skipIf(pep8 is None, 'No pep8 package available')
    def test_pep8_clean(self):
        # https://github.com/jcrocholl/pep8/issues/103
        pep8_style = pep8.StyleGuide(ignore='E123')
        result = pep8_style.check_files(self.all_paths())
        self.assertEqual(result.total_errors, 0)

    @skipIf('SKIP_SLOW_TESTS' in os.environ, 'Skipping slow tests')
    @skipIf(pyflakes is None, 'No pyflakes package available')
    def test_pyflakes_clean(self):
        reporter = pyflakes.reporter.Reporter(sys.stdout, sys.stderr)
        warnings = pyflakes.api.checkRecursive(self.all_paths(), reporter)
        self.assertEqual(0, warnings)
