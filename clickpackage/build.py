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

"""Building Click packages."""

from __future__ import print_function

__metaclass__ = type

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from textwrap import dedent

from clickpackage import osextras
from clickpackage.arfile import ArFile
from clickpackage.preinst import static_preinst
from clickpackage.versions import base_version, spec_version


@contextlib.contextmanager
def make_temp_dir():
    temp_dir = tempfile.mkdtemp(prefix="clickpackage")
    try:
        os.chmod(temp_dir, 0o755)
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


class FakerootTarFile(tarfile.TarFile):
    """A version of TarFile which pretends all files are owned by root:root."""

    def gettarinfo(self, *args, **kwargs):
        tarinfo = super(FakerootTarFile, self).gettarinfo(*args, **kwargs)
        tarinfo.uid = tarinfo.gid = 0
        tarinfo.uname = tarinfo.gname = "root"
        return tarinfo


class ClickBuilder:
    def __init__(self):
        self.file_map = {}

    def add_file(self, source_path, dest_path):
        self.file_map[source_path] = dest_path

    def list_files(self, root_path):
        for dirpath, _, filenames in os.walk(root_path):
            rel_dirpath = os.path.relpath(dirpath, root_path)
            if rel_dirpath == ".":
                rel_dirpath = ""
            for filename in filenames:
                yield os.path.join(rel_dirpath, filename)

    def read_metadata(self, metadata_path):
        with open(metadata_path) as metadata:
            self.metadata = json.load(metadata)
        self.name = self.metadata["name"]
        self.version = self.metadata["version"]
        self.maintainer = self.metadata["maintainer"]
        self.description = self.metadata["description"]
        self.architecture = self.metadata.get("architecture", "all")

    def _filter_dot_click(self, tarinfo):
        """Filter out attempts to include .click at the top level."""
        if tarinfo.name == "./.click" or tarinfo.name.startswith("./.click/"):
            return None
        return tarinfo

    def build(self, dest_dir, metadata_path=None):
        with make_temp_dir() as temp_dir:
            # Data area
            root_path = os.path.join(temp_dir, "data")
            for source_path, dest_path in self.file_map.items():
                if dest_path.startswith("/"):
                    dest_path = dest_path[1:]
                real_dest_path = os.path.join(root_path, dest_path)
                shutil.copytree(source_path, real_dest_path)

            real_metadata_path = os.path.join(root_path, "metadata.json")
            if metadata_path is not None:
                shutil.copy2(metadata_path, real_metadata_path)
            os.chmod(real_metadata_path, 0o644)
            self.read_metadata(real_metadata_path)

            data_tar_path = os.path.join(temp_dir, "data.tar.gz")
            data_tar = FakerootTarFile.open(
                name=data_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT)
            data_tar.add(
                root_path, arcname="./", filter=self._filter_dot_click)
            data_tar.close()

            # Control area
            du_output = subprocess.check_output(
                ["du", "-k", "-s", "--apparent-size", "."],
                cwd=temp_dir, universal_newlines=True).rstrip("\n")
            match = re.match(r"^(\d+)\s+\.$", du_output)
            if not match:
                raise Exception("du gave unexpected output '%s'" % du_output)
            installed_size = match.group(1)
            control_dir = os.path.join(temp_dir, "DEBIAN")
            control_path = os.path.join(control_dir, "control")
            osextras.ensuredir(os.path.dirname(control_path))
            with open(control_path, "w") as control:
                print(dedent("""\
                    Package: %s
                    Version: %s
                    Click-Version: %s
                    Click-Base-System: %s
                    Architecture: %s
                    Maintainer: %s
                    Installed-Size: %s
                    Description: %s""" % (
                    self.name, self.version, spec_version, base_version,
                    self.architecture, self.maintainer, installed_size,
                    self.description)),
                    file=control)
            md5sums_path = os.path.join(control_dir, "md5sums")
            with open(md5sums_path, "w") as md5sums:
                for path in sorted(self.list_files(root_path)):
                    md5 = hashlib.md5()
                    with open(os.path.join(root_path, path), "rb") as f:
                        while True:
                            buf = f.read(16384)
                            if not buf:
                                break
                            md5.update(buf)
                    print("%s  %s" % (md5.hexdigest(), path), file=md5sums)
            preinst_path = os.path.join(control_dir, "preinst")
            with open(preinst_path, "w") as preinst:
                preinst.write(static_preinst)
            control_tar_path = os.path.join(temp_dir, "control.tar.gz")
            control_tar = tarfile.open(
                name=control_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT)
            control_tar.add(control_dir, arcname="./")
            control_tar.close()

            # TODO: strip epoch from version, or disallow epochs?
            package_name = "%s_%s_%s.click" % (
                self.name, self.version, self.architecture)
            package_path = os.path.join(dest_dir, package_name)
            with ArFile(name=package_path, mode="w") as package:
                package.add_magic()
                package.add_data("debian-binary", b"2.0\n")
                package.add_file("control.tar.gz", control_tar_path)
                package.add_file("data.tar.gz", data_tar_path)
            return package_path
