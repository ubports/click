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

"""Integration tests for the click install feature."""

import os
import subprocess
import unittest

from .helpers import TestCase


def add_user(name):
    subprocess.check_call(["useradd", name])
    return name


def del_user(name):
    subprocess.check_call(["userdel", "-r", name])


@unittest.skipIf(
    os.getuid() != 0, "This tests needs to run as root")
class TestClickInstall(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestClickInstall, cls).setUpClass()
        cls.USER_1 = add_user("click-test-user-1")
        cls.USER_2 = add_user("click-test-user-2")

    @classmethod
    def tearDownClass(cls):
        super(TestClickInstall, cls).tearDownClass()
        del_user(cls.USER_1)
        del_user(cls.USER_2)

    def click_unregister(self, username, click_name):
        if username == "@all":
            user = "--all-users"
        else:
            user = "--user=%s" % username
        subprocess.check_call(
            [self.click_binary, "unregister", user, click_name])

    def test_install_for_single_user(self):
        click_pkg = self._make_click(name="foo-1", framework="")
        # install it
        subprocess.check_call([
            self.click_binary, "install", "--user=%s" % self.USER_1,
            click_pkg], universal_newlines=True)
        self.addCleanup(self.click_unregister, self.USER_1, "foo-1")
        # ensure that user-1 has it
        output = subprocess.check_output([
            "sudo", "-u", self.USER_1,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "foo-1\t1.0\n")
        # but not user-2
        output = subprocess.check_output([
            "sudo", "-u", self.USER_2,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "")
        # and that we can see it with the --user option
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.USER_1],
            universal_newlines=True)
        self.assertEqual(output, "foo-1\t1.0\n")

    def test_install_for_all_users(self):
        click_pkg = self._make_click(name="foo-2", framework="")
        # install it
        subprocess.check_call(
            [self.click_binary, "install", "--all-users",  click_pkg],
            universal_newlines=True)
        self.addCleanup(self.click_unregister, "@all", "foo-2")
        # ensure all users see it
        for user in (self.USER_1, self.USER_2):
            output = subprocess.check_output(
                ["sudo", "-u", user, self.click_binary, "list"],
                universal_newlines=True)
            self.assertEqual(output, "foo-2\t1.0\n")

    def test_pkgdir_after_install(self):
        click_pkg = self._make_click(name="foo-2", version="1.2", framework="")
        subprocess.check_call(
            [self.click_binary, "install", "--all-users",  click_pkg],
            universal_newlines=True)
        self.addCleanup(self.click_unregister, "@all", "foo-2")
        # from the path
        output = subprocess.check_output(
            [self.click_binary, "pkgdir",
             "/opt/click.ubuntu.com/foo-2/1.2/README"],
            universal_newlines=True).strip()
        self.assertEqual(output, "/opt/click.ubuntu.com/foo-2/1.2")
        # now test from the click package name
        output = subprocess.check_output(
            [self.click_binary, "pkgdir", "foo-2"],
            universal_newlines=True).strip()
        # note that this is different from above
        self.assertEqual(
            output, "/opt/click.ubuntu.com/.click/users/@all/foo-2")
