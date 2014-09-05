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

import subprocess

from .helpers import (
    require_root,
    ClickTestCase,
)


def add_user(name):
    subprocess.check_call(["useradd", name])
    return name


def del_user(name):
    subprocess.check_call(["userdel", "-r", name])


class TestClickInstall(ClickTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestClickInstall, cls).setUpClass()
        require_root()
        cls.USER_1 = add_user("click-test-user-1")
        cls.USER_2 = add_user("click-test-user-2")

    @classmethod
    def tearDownClass(cls):
        super(TestClickInstall, cls).tearDownClass()
        del_user(cls.USER_1)
        del_user(cls.USER_2)

    def test_install_for_single_user(self):
        name = "foo-1"
        click_pkg = self._make_click(name=name, framework="")
        # install it
        self.click_install(click_pkg, name, self.USER_1)
        # ensure that user-1 has it
        output = subprocess.check_output([
            "sudo", "-u", self.USER_1,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "%s\t1.0\n" % name)
        # but not user-2
        output = subprocess.check_output([
            "sudo", "-u", self.USER_2,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "")
        # and that we can see it with the --user option
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.USER_1],
            universal_newlines=True)
        self.assertEqual(output, "%s\t1.0\n" % name)

    def test_install_for_single_user_and_register(self):
        name = "foo-1"
        click_pkg = self._make_click(name=name, framework="")
        self.click_install(click_pkg, name, self.USER_1)
        # not available for user2
        output = subprocess.check_output([
            "sudo", "-u", self.USER_2,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "")
        # register it
        subprocess.check_call(
            [self.click_binary, "register", "--user=%s" % self.USER_2,
             name, "1.0", ])
        self.addCleanup(self.click_unregister, name, self.USER_2)
        # and ensure its available for user2
        output = subprocess.check_output([
            "sudo", "-u", self.USER_2,
            self.click_binary, "list"], universal_newlines=True)
        self.assertEqual(output, "%s\t1.0\n" % name)

    def test_install_for_all_users(self):
        name = "foo-2"
        click_pkg = self._make_click(name=name, framework="")
        self.click_install(click_pkg, name, "@all")
        # ensure all users see it
        for user in (self.USER_1, self.USER_2):
            output = subprocess.check_output(
                ["sudo", "-u", user, self.click_binary, "list"],
                universal_newlines=True)
            self.assertEqual(output, "%s\t1.0\n" % name)

    def test_pkgdir_after_install(self):
        name = "foo-3"
        click_pkg = self._make_click(name=name, version="1.2", framework="")
        self.click_install(click_pkg, name, "@all")
        # from the path
        output = subprocess.check_output(
            [self.click_binary, "pkgdir",
             "/opt/click.ubuntu.com/%s/1.2/README" % name],
            universal_newlines=True).strip()
        self.assertEqual(output, "/opt/click.ubuntu.com/%s/1.2" % name)
        # now test from the click package name
        output = subprocess.check_output(
            [self.click_binary, "pkgdir", name],
            universal_newlines=True).strip()
        # note that this is different from above
        self.assertEqual(
            output, "/opt/click.ubuntu.com/.click/users/@all/%s" % name)
