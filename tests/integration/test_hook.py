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

"""Integration tests for the click hook feature."""

import os
import subprocess
from textwrap import dedent
import unittest

from .helpers import (
    is_root,
    ClickTestCase,
)


@unittest.skipIf(not is_root(), "This tests needs to run as root")
class TestHook(ClickTestCase):
    def _make_hook(self, name):
        hook_fname = "/usr/share/click/hooks/%s.hook" % name
        canary_fname = os.path.join(self.temp_dir, "canary.sh")
        canary_log = os.path.join(self.temp_dir, "canary.log")
        with open(hook_fname, "w") as f:
            f.write(dedent("""\
            Pattern: ${home}/${id}.test-hook
            User-Level: yes
            Exec: %s
            Hook-Name: %s
            """ % (canary_fname, name)))
        with open(canary_fname, "w") as f:
            f.write(dedent("""\
            #!/bin/sh
            echo "i-hook-you-up" >> %s
            """ % canary_log))
        os.chmod(canary_fname, 0o755)
        return hook_fname, canary_log

    def test_hook_install_user(self):
        # build/install the hook
        hook_name = "clicktesthook"
        hook_file, hook_log = self._make_hook(hook_name)
        self.addCleanup(os.unlink, hook_file)
        subprocess.check_call(
            [self.click_binary, "hook", "install", hook_name])
        self.addCleanup(
            subprocess.check_call, [self.click_binary, "hook", "remove",
                                    hook_name])
        # make click that uses the hook
        hooks = {'app1': {hook_name: 'README'}}
        click_pkg_name = "com.example.hook-1"
        click_pkg = self._make_click(
            click_pkg_name, framework="", hooks=hooks)
        user = os.environ.get("USER", "root")
        subprocess.check_call(
            [self.click_binary, "install", "--user=%s" % user, click_pkg],
            universal_newlines=True)
        self.addCleanup(
            subprocess.check_call,
            [self.click_binary, "unregister", "--user=%s" % user,
             click_pkg_name])
        # ensure we have the hook
        generated_hook_file = os.path.expanduser(
            "~/com.example.hook-1_app1_1.0.test-hook")
        self.assertTrue(os.path.exists(generated_hook_file))
        self.assertEqual(
            os.path.realpath(generated_hook_file),
            "/opt/click.ubuntu.com/com.example.hook-1/1.0/README")
        with open(hook_log) as f:
            hook_log_content = f.read().strip()
        self.assertEqual("i-hook-you-up", hook_log_content)
