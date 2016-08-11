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

import copy
import os
import shutil
import subprocess
import tarfile
from textwrap import dedent

import apt

from .helpers import (
    require_root,
    ClickTestCase,
)


def makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        pass


def get_keyid_from_gpghome(gpg_home):
    """Return the public keyid of a given gpg home dir"""
    output = subprocess.check_output(
        ["gpg", "--home", gpg_home, "--list-keys", "--with-colons"],
        universal_newlines=True)
    for line in output.splitlines():
        if not line.startswith("pub:"):
            continue
        return line.split(":")[4]
    raise ValueError("Cannot find public key in output: '%s'" % output)


class Debsigs:
    """Tiny wrapper around the debsigs CLI"""
    def __init__(self, gpghome, keyid):
        self.keyid = keyid
        self.gpghome = gpghome
        self.policy = "/etc/debsig/policies/%s/generic.pol" % self.keyid

    def sign(self, filepath, signature_type="origin"):
        """Sign the click at filepath"""
        env = copy.copy(os.environ)
        env["GNUPGHOME"] = os.path.abspath(self.gpghome)
        subprocess.check_call(
            ["debsigs",
             "--sign=%s" % signature_type,
             "--default-key=%s" % self.keyid,
             filepath], env=env)

    def install_signature_policy(self):
        """Install/update the system-wide signature policy"""
        if apt.Cache()["debsig-verify"].installed >= "0.15":
            debsig_xmlns = "https://www.debian.org/debsig/1.0/"
        else:
            debsig_xmlns = "http://www.debian.org/debsig/1.0/"
        xmls = dedent("""\
        <?xml version="1.0"?>
        <!DOCTYPE Policy SYSTEM "{debsig_xmlns}policy.dtd">
        <Policy xmlns="{debsig_xmlns}">

        <Origin Name="test-origin" id="{keyid}" Description="Example policy"/>
        <Selection>
        <Required Type="origin" File="{filename}" id="{keyid}"/>
        </Selection>

        <Verification>
        <Required Type="origin" File="{filename}" id="{keyid}"/>
        </Verification>
        </Policy>
        """.format(
            debsig_xmlns=debsig_xmlns, keyid=self.keyid,
            filename="origin.pub"))
        makedirs(os.path.dirname(self.policy))
        with open(self.policy, "w") as f:
            f.write(xmls)
        self.pubkey_path = (
            "/usr/share/debsig/keyrings/%s/origin.pub" % self.keyid)
        makedirs(os.path.dirname(self.pubkey_path))
        shutil.copy(
            os.path.join(self.gpghome, "pubring.gpg"), self.pubkey_path)

    def uninstall_signature_policy(self):
        # FIXME: update debsig-verify so that it can work from a different
        #        root than "/" so that the tests do not have to use the
        #        system root
        os.remove(self.policy)
        os.remove(self.pubkey_path)


class ClickSignaturesTestCase(ClickTestCase):

    @classmethod
    def setUpClass(cls):
        super(ClickSignaturesTestCase, cls).setUpClass()
        require_root()

    def assertClickNoSignatureError(self, cmd_args):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            output = subprocess.check_output(
                [self.click_binary] + cmd_args,
                stderr=subprocess.STDOUT, universal_newlines=True)
        output = cm.exception.output
        expected_error_message = ("debsig: Origin Signature check failed. "
                                  "This deb might not be signed.")
        self.assertIn(expected_error_message, output)

    def assertClickInvalidSignatureError(self, cmd_args):
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            output = subprocess.check_output(
                [self.click_binary] + cmd_args,
                stderr=subprocess.STDOUT, universal_newlines=True)
            print(output)

        output = cm.exception.output
        expected_error_message = "Signature verification error: "
        self.assertIn(expected_error_message, output)


class TestSignatureVerificationNoSignature(ClickSignaturesTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestSignatureVerificationNoSignature, cls).setUpClass()
        require_root()

    def test_debsig_verify_no_sig(self):
        name = "org.example.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        self.assertClickNoSignatureError(["verify", path_to_click])

    def test_debsig_install_no_sig(self):
        name = "org.example.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        self.assertClickNoSignatureError(["install", path_to_click])

    def test_debsig_install_can_install_with_sig_override(self):
        name = "org.example.debsig-no-sig"
        path_to_click = self._make_click(name, framework="")
        user = os.environ.get("USER", "root")
        subprocess.check_call(
            [self.click_binary, "install",
             "--allow-unauthenticated", "--user=%s" % user,
             path_to_click])
        self.addCleanup(
            subprocess.call, [self.click_binary, "unregister",
                              "--user=%s" % user, name])


class TestSignatureVerification(ClickSignaturesTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestSignatureVerification, cls).setUpClass()
        require_root()

    def setUp(self):
        super(TestSignatureVerification, self).setUp()
        self.user = os.environ.get("USER", "root")
        # the valid origin keyring
        self.datadir = os.path.join(os.path.dirname(__file__), "data")
        origin_keyring_dir = os.path.abspath(
            os.path.join(self.datadir, "origin-keyring"))
        keyid = get_keyid_from_gpghome(origin_keyring_dir)
        self.debsigs = Debsigs(origin_keyring_dir, keyid)
        self.debsigs.install_signature_policy()

    def tearDown(self):
        self.debsigs.uninstall_signature_policy()

    def test_debsig_install_valid_signature(self):
        name = "org.example.debsig-valid-sig"
        path_to_click = self._make_click(name, framework="")
        self.debsigs.sign(path_to_click)
        subprocess.check_call(
            [self.click_binary, "install",
             "--user=%s" % self.user,
             path_to_click])
        self.addCleanup(
            subprocess.call, [self.click_binary, "unregister",
                              "--user=%s" % self.user, name])
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertIn(name, output)

    def test_debsig_install_signature_not_in_keyring(self):
        name = "org.example.debsig-no-keyring-sig"
        path_to_click = self._make_click(name, framework="")
        evil_keyring_dir = os.path.join(self.datadir, "evil-keyring")
        keyid = get_keyid_from_gpghome(evil_keyring_dir)
        debsig_bad = Debsigs(evil_keyring_dir, keyid)
        debsig_bad.sign(path_to_click)
        # and ensure its really not there
        self.assertClickInvalidSignatureError(["install", path_to_click])
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertNotIn(name, output)

    def test_debsig_install_not_a_signature(self):
        name = "org.example.debsig-invalid-sig"
        path_to_click = self._make_click(name, framework="")
        invalid_sig = os.path.join(self.temp_dir, "_gpgorigin")
        with open(invalid_sig, "w") as f:
            f.write("no-valid-signature")
        # add a invalid sig
        subprocess.check_call(["ar", "-r", path_to_click, invalid_sig])
        self.assertClickInvalidSignatureError(["install", path_to_click])
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertNotIn(name, output)

    def test_debsig_install_signature_altered_click(self):
        def modify_ar_member(member):
            subprocess.check_call(
                ["ar", "-x", path_to_click, "control.tar.gz"],
                cwd=self.temp_dir)
            altered_member = os.path.join(self.temp_dir, member)
            with open(altered_member, "ba") as f:
                f.write(b"\0")
            subprocess.check_call(["ar", "-r", path_to_click, altered_member])

        # ensure that all members we care about are checked by debsig-verify
        for member in ["control.tar.gz", "data.tar.gz", "debian-binary"]:
            name = "org.example.debsig-altered-click"
            path_to_click = self._make_click(name, framework="")
            self.debsigs.sign(path_to_click)
            modify_ar_member(member)
            self.assertClickInvalidSignatureError(["install", path_to_click])
            output = subprocess.check_output(
                [self.click_binary, "list", "--user=%s" % self.user],
                universal_newlines=True)
            self.assertNotIn(name, output)

    def make_nasty_data_tar(self, compression):
        new_data_tar = os.path.join(self.temp_dir, "data.tar." + compression)
        evilfile = os.path.join(self.temp_dir, "README.evil")
        with open(evilfile, "w") as f:
            f.write("I am a nasty README")
        with tarfile.open(new_data_tar, "w:"+compression) as tar:
            tar.add(evilfile)
        return new_data_tar

    def test_debsig_install_signature_injected_data_tar(self):
        name = "org.example.debsig-injected-data-click"
        path_to_click = self._make_click(name, framework="")
        self.debsigs.sign(path_to_click)
        new_data = self.make_nasty_data_tar("bz2")
        # insert before the real data.tar.gz and ensure this is caught
        # NOTE: that right now this will not be caught by debsig-verify
        #        but later in audit() by debian.debfile.DebFile()
        subprocess.check_call(["ar",
                               "-r",
                               "-b", "data.tar.gz",
                               path_to_click,
                               new_data])
        output = subprocess.check_output(
            ["ar", "-t", path_to_click], universal_newlines=True)
        self.assertEqual(output.splitlines(),
                         ["debian-binary",
                          "_click-binary",
                          "control.tar.gz",
                          "data.tar.bz2",
                          "data.tar.gz",
                          "_gpgorigin"])
        with self.assertRaises(subprocess.CalledProcessError):
            output = subprocess.check_output(
                [self.click_binary, "install", path_to_click],
                stderr=subprocess.STDOUT, universal_newlines=True)
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertNotIn(name, output)

    def test_debsig_install_signature_replaced_data_tar(self):
        name = "org.example.debsig-replaced-data-click"
        path_to_click = self._make_click(name, framework="")
        self.debsigs.sign(path_to_click)
        new_data = self.make_nasty_data_tar("bz2")
        # replace data.tar.gz with data.tar.bz2 and ensure this is caught
        subprocess.check_call(["ar",
                               "-d",
                               path_to_click,
                               "data.tar.gz",
                               ])
        subprocess.check_call(["ar",
                               "-r",
                               path_to_click,
                               new_data])
        output = subprocess.check_output(
            ["ar", "-t", path_to_click], universal_newlines=True)
        self.assertEqual(output.splitlines(),
                         ["debian-binary",
                          "_click-binary",
                          "control.tar.gz",
                          "_gpgorigin",
                          "data.tar.bz2",
                          ])
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            output = subprocess.check_output(
                [self.click_binary, "install", path_to_click],
                stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertIn("Signature verification error", cm.exception.output)
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertNotIn(name, output)

    def test_debsig_install_signature_prepend_sig(self):
        # this test is probably not really needed, it tries to trick
        # the system by prepending a valid signature that is not
        # in the keyring. But given that debsig-verify only reads
        # the first packet of any given _gpg$foo signature it's
        # equivalent to test_debsig_install_signature_not_in_keyring test
        name = "org.example.debsig-replaced-data-prepend-sig-click"
        path_to_click = self._make_click(name, framework="")
        self.debsigs.sign(path_to_click)
        new_data = self.make_nasty_data_tar("gz")
        # replace data.tar.gz
        subprocess.check_call(["ar",
                               "-r",
                               path_to_click,
                               new_data,
                               ])
        # get previous good _gpgorigin for the old data
        subprocess.check_call(
            ["ar", "-x", path_to_click, "_gpgorigin"], cwd=self.temp_dir)
        with open(os.path.join(self.temp_dir, "_gpgorigin"), "br") as f:
            good_gpg_origin = f.read()
        # and append a valid signature from a non-keyring key
        evil_keyring_dir = os.path.join(self.datadir, "evil-keyring")
        debsig_bad = Debsigs(evil_keyring_dir, "18B38B9AC1B67A0D")
        debsig_bad.sign(path_to_click)
        subprocess.check_call(
            ["ar", "-x", path_to_click, "_gpgorigin"], cwd=self.temp_dir)
        with open(os.path.join(self.temp_dir, "_gpgorigin"), "br") as f:
            evil_gpg_origin = f.read()
        with open(os.path.join(self.temp_dir, "_gpgorigin"), "wb") as f:
            f.write(evil_gpg_origin)
            f.write(good_gpg_origin)
        subprocess.check_call(
            ["ar", "-r", path_to_click, "_gpgorigin"], cwd=self.temp_dir)
        # now ensure that the verification fails as well
        with self.assertRaises(subprocess.CalledProcessError) as cm:
            output = subprocess.check_output(
                [self.click_binary, "install", path_to_click],
                stderr=subprocess.STDOUT, universal_newlines=True)
        self.assertIn("Signature verification error", cm.exception.output)
        output = subprocess.check_output(
            [self.click_binary, "list", "--user=%s" % self.user],
            universal_newlines=True)
        self.assertNotIn(name, output)
