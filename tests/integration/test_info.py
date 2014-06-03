#!/usr/bin/python

import copy
import contextlib
import glob
import json
import os
import os.path
import random
import re
import shutil
import string
import subprocess
import sys
import tempfile
import unittest


@contextlib.contextmanager
def chdir(target):
    curdir = os.getcwd()
    os.chdir(target)
    yield
    os.chdir(curdir)


class TestClickInfo(unittest.TestCase):

    def setUp(self):
        self.saved_env = copy.copy(os.environ)
        os.environ["PYTHONPATH"] = os.path.abspath(
            os.path.join(sys.argv[0], ".."))
        self.click_binary = os.path.abspath(
            os.path.join(sys.argv[0], "..", "bin", "click"))

    def tearDown(self):
        os.environ = self.saved_env

    def _make_click(self, name=None, version=1.0):
        if name is None:
            name = "com.ubuntu.%s" % "".join(random.choice(string.lowercase) 
                                             for i in range(10))
        tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmpdir))
        clickdir = os.path.join(tmpdir, name)
        os.makedirs(clickdir)
        with open(os.path.join(clickdir, "manifest.json"), "w") as f:
            f.write("""{
            "name": "%s",
            "version": "%s",
            "maintainer": "Foo Bar <foo@example.org>",
            "title": "test title",
            "framework": "ubuntu-sdk-13.10"
            }""" % (name, version))
        with open(os.path.join(clickdir, "README"), "w") as f:
            f.write("hello world!")
        with chdir(tmpdir), open(os.devnull, "w") as devnull:
            subprocess.call(["click", "build", clickdir], stdout=devnull)
        generated_clicks = glob.glob(os.path.join(tmpdir, "*.click"))
        self.assertEqual(len(generated_clicks), 1)
        return generated_clicks[0]

    def test_build(self):
        path_to_click = self._make_click()
        self.assertTrue(os.path.exists(path_to_click))

    def test_info(self):
        name = "com.ubuntu.foo"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "info", path_to_click])
        self.assertEqual(json.loads(output)["name"], name)

    def test_verify_ok(self):
        name = "com.ubuntu.verify-ok"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "verify", path_to_click])
        self.assertEqual(output, "")

    def test_contents(self):
        name = "com.ubuntu.contents"
        path_to_click = self._make_click(name)
        output = subprocess.check_output([
            self.click_binary, "contents", path_to_click])
        self.assertTrue(re.search(
            r'-rw-rw-r-- root/root\s+[0-9]+\s+[0-9-]+ [0-9:]+ ./README', output))
