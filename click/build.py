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
__all__ = [
    'ClickBuilder',
    'ClickSourceBuilder',
    ]


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

from click import osextras
from click.arfile import ArFile
from click.preinst import static_preinst
from click.versions import spec_version


@contextlib.contextmanager
def make_temp_dir():
    temp_dir = tempfile.mkdtemp(prefix="click")
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


class ClickBuilderBase:
    def __init__(self):
        self.file_map = {}

    def add_file(self, source_path, dest_path):
        self.file_map[source_path] = dest_path

    def read_manifest(self, manifest_path):
        with open(manifest_path) as manifest:
            self.manifest = json.load(manifest)

    @property
    def name(self):
        return self.manifest["name"]

    @property
    def version(self):
        return self.manifest["version"]

    @property
    def epochless_version(self):
        return re.sub(r"^\d+:", "", self.version)

    @property
    def maintainer(self):
        return self.manifest["maintainer"]

    @property
    def title(self):
        return self.manifest["title"]

    @property
    def architecture(self):
        return self.manifest.get("architecture", "all")


class ClickBuilder(ClickBuilderBase):
    def list_files(self, root_path):
        for dirpath, _, filenames in os.walk(root_path):
            rel_dirpath = os.path.relpath(dirpath, root_path)
            if rel_dirpath == ".":
                rel_dirpath = ""
            for filename in filenames:
                yield os.path.join(rel_dirpath, filename)

    def _filter_dot_click(self, tarinfo):
        """Filter out attempts to include .click at the top level."""
        if tarinfo.name == './.click' or tarinfo.name.startswith('./.click/'):
            return None
        return tarinfo

    def build(self, dest_dir, manifest_path="manifest.json"):
        with make_temp_dir() as temp_dir:
            # Prepare data area.
            root_path = os.path.join(temp_dir, "data")

            for source_path, dest_path in self.file_map.items():
                if dest_path.startswith("/"):
                    dest_path = dest_path[1:]
                real_dest_path = os.path.join(root_path, dest_path)
                shutil.copytree(source_path, real_dest_path, symlinks=True)

            # Prepare control area.
            control_dir = os.path.join(temp_dir, "DEBIAN")
            osextras.ensuredir(control_dir)

            # Control file names must not contain a dot, hence "manifest"
            # rather than "manifest.json" in the control area.
            real_manifest_path = os.path.join(control_dir, "manifest")
            if os.path.isabs(manifest_path):
                full_manifest_path = manifest_path
            else:
                full_manifest_path = os.path.join(root_path, manifest_path)
            os.rename(full_manifest_path, real_manifest_path)
            os.chmod(real_manifest_path, 0o644)
            self.read_manifest(real_manifest_path)

            du_output = subprocess.check_output(
                ["du", "-k", "-s", "--apparent-size", "."],
                cwd=temp_dir, universal_newlines=True).rstrip("\n")
            match = re.match(r"^(\d+)\s+\.$", du_output)
            if not match:
                raise Exception("du gave unexpected output '%s'" % du_output)
            installed_size = match.group(1)
            control_path = os.path.join(control_dir, "control")
            osextras.ensuredir(os.path.dirname(control_path))
            with open(control_path, "w") as control:
                print(dedent("""\
                    Package: %s
                    Version: %s
                    Click-Version: %s
                    Architecture: %s
                    Maintainer: %s
                    Installed-Size: %s
                    Description: %s""" % (
                    self.name, self.version, spec_version, self.architecture,
                    self.maintainer, installed_size, self.title)),
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

            # Pack everything up.
            data_tar_path = os.path.join(temp_dir, "data.tar.gz")
            with contextlib.closing(FakerootTarFile.open(
                    name=data_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT
                    )) as data_tar:
                data_tar.add(
                    root_path, arcname="./", filter=self._filter_dot_click)

            control_tar_path = os.path.join(temp_dir, "control.tar.gz")
            control_tar = tarfile.open(
                name=control_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT)
            control_tar.add(control_dir, arcname="./")
            control_tar.close()

            package_name = "%s_%s_%s.click" % (
                self.name, self.epochless_version, self.architecture)
            package_path = os.path.join(dest_dir, package_name)
            with ArFile(name=package_path, mode="w") as package:
                package.add_magic()
                package.add_data("debian-binary", b"2.0\n")
                package.add_file("control.tar.gz", control_tar_path)
                package.add_file("data.tar.gz", data_tar_path)
            return package_path


class ClickSourceBuilder(ClickBuilderBase):
    # From @Dpkg::Source::Package::tar_ignore_default_pattern.
    # TODO: This should be configurable, or at least extensible.
    _ignore_patterns = [
        "*.a",
        "*.la",
        "*.o",
        "*.so",
        ".*.sw?",
        "*~",
        ",,*",
        ".[#~]*",
        ".arch-ids",
        ".arch-inventory",
        ".be",
        ".bzr",
        ".bzr-builddeb",
        ".bzr.backup",
        ".bzr.tags",
        ".bzrignore",
        ".cvsignore",
        ".deps",
        ".git",
        ".gitattributes",
        ".gitignore",
        ".gitmodules",
        ".hg",
        ".hgignore",
        ".hgsigs",
        ".hgtags",
        ".shelf",
        ".svn",
        "CVS",
        "DEADJOE",
        "RCS",
        "_MTN",
        "_darcs",
        "{arch}",
        ]

    def build(self, dest_dir, manifest_path=None):
        with make_temp_dir() as temp_dir:
            root_path = os.path.join(temp_dir, "source")
            for source_path, dest_path in self.file_map.items():
                if dest_path.startswith("/"):
                    dest_path = dest_path[1:]
                real_dest_path = os.path.join(root_path, dest_path)
                shutil.copytree(
                    source_path, real_dest_path, symlinks=True,
                    ignore=shutil.ignore_patterns(*self._ignore_patterns))

            real_manifest_path = os.path.join(root_path, "manifest.json")
            if manifest_path is not None:
                shutil.copy2(manifest_path, real_manifest_path)
            os.chmod(real_manifest_path, 0o644)
            self.read_manifest(real_manifest_path)

            package_name = "%s_%s.tar.gz" % (self.name, self.epochless_version)
            package_path = os.path.join(dest_dir, package_name)
            with contextlib.closing(FakerootTarFile.open(
                    name=package_path, mode="w:gz", format=tarfile.GNU_FORMAT
                    )) as tar:
                tar.add(root_path, arcname="./")
            return package_path
