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
    'ClickBuildError',
    'ClickBuilder',
    'ClickSourceBuilder',
    ]


import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from textwrap import dedent

try:
    import apt_pkg
    apt_pkg.init_system()
except ImportError:
    # "click build" is required to work with only the Python standard library.
    pass

from click_package import osextras
from click_package.arfile import ArFile
from click_package.preinst import static_preinst
from click_package.versions import spec_version

from click_package.framework import (
    validate_framework,
    ClickFrameworkInvalid,
)


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


class ClickBuildError(Exception):
    pass


class ClickBuilderBase:
    def __init__(self):
        self.file_map = {}
        # From @Dpkg::Source::Package::tar_ignore_default_pattern.
        # (more in ClickSourceBuilder)
        self._ignore_patterns = [
            "*.click",
            ".*.sw?",
            "*~",
            ",,*",
            ".[#~]*",
            ".arch-ids",
            ".arch-inventory",
            ".bzr",
            ".bzr-builddeb",
            ".bzr.backup",
            ".bzr.tags",
            ".bzrignore",
            ".cvsignore",
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

    def add_ignore_pattern(self, pattern):
        self._ignore_patterns.append(pattern)

    def add_file(self, source_path, dest_path):
        self.file_map[source_path] = dest_path

    def read_manifest(self, manifest_path):
        with io.open(manifest_path, encoding="UTF-8") as manifest:
            try:
                self.manifest = json.load(manifest)
            except Exception as e:
                raise ClickBuildError(
                    "Error reading manifest from %s: %s" % (manifest_path, e))
            keys = sorted(self.manifest)
            for key in keys:
                if key.startswith("_"):
                    print(
                        "Ignoring reserved dynamic key '%s'." % key,
                        file=sys.stderr)
                    del self.manifest[key]

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
        manifest_arch = self.manifest.get("architecture", "all")
        if isinstance(manifest_arch, list):
            return "multi"
        else:
            return manifest_arch


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

    def _pack(self, temp_dir, control_dir, data_dir, package_path):
        data_tar_path = os.path.join(temp_dir, "data.tar.gz")
        with contextlib.closing(FakerootTarFile.open(
                name=data_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT
                )) as data_tar:
            data_tar.add(data_dir, arcname="./", filter=self._filter_dot_click)

        control_tar_path = os.path.join(temp_dir, "control.tar.gz")
        control_tar = tarfile.open(
            name=control_tar_path, mode="w:gz", format=tarfile.GNU_FORMAT)
        control_tar.add(control_dir, arcname="./")
        control_tar.close()

        with ArFile(name=package_path, mode="w") as package:
            package.add_magic()
            package.add_data("debian-binary", b"2.0\n")
            package.add_data(
                "_click-binary", ("%s\n" % spec_version).encode("UTF-8"))
            package.add_file("control.tar.gz", control_tar_path)
            package.add_file("data.tar.gz", data_tar_path)

    def _validate_framework(self, framework_string):
        """Apply policy checks to framework declarations."""
        try:
            validate_framework(
                framework_string, ignore_missing_frameworks=True)
        except ClickFrameworkInvalid as e:
            raise ClickBuildError(str(e))

    def build(self, dest_dir, manifest_path="manifest.json"):
        with make_temp_dir() as temp_dir:
            # Prepare data area.
            root_path = os.path.join(temp_dir, "data")

            for source_path, dest_path in self.file_map.items():
                if dest_path.startswith("/"):
                    dest_path = dest_path[1:]
                real_dest_path = os.path.join(root_path, dest_path)
                shutil.copytree(
                    source_path, real_dest_path, symlinks=True,
                    ignore=shutil.ignore_patterns(*self._ignore_patterns))

            # Prepare control area.
            control_dir = os.path.join(temp_dir, "DEBIAN")
            osextras.ensuredir(control_dir)

            if os.path.isabs(manifest_path):
                full_manifest_path = manifest_path
            else:
                full_manifest_path = os.path.join(root_path, manifest_path)
            self.read_manifest(full_manifest_path)
            if "framework" in self.manifest:
                self._validate_framework(self.manifest["framework"])

            du_output = subprocess.check_output(
                ["du", "-k", "-s", "--apparent-size", "."],
                cwd=temp_dir, universal_newlines=True).rstrip("\n")
            match = re.match(r"^(\d+)\s+\.$", du_output)
            if not match:
                raise Exception("du gave unexpected output '%s'" % du_output)
            installed_size = match.group(1)
            self.manifest["installed-size"] = installed_size
            control_path = os.path.join(control_dir, "control")
            osextras.ensuredir(os.path.dirname(control_path))
            with io.open(control_path, "w", encoding="UTF-8") as control:
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

            # Control file names must not contain a dot, hence "manifest"
            # rather than "manifest.json" in the control area.
            real_manifest_path = os.path.join(control_dir, "manifest")
            with io.open(
                    real_manifest_path, "w", encoding="UTF-8") as manifest:
                print(
                    json.dumps(
                        self.manifest, ensure_ascii=False, sort_keys=True,
                        indent=4, separators=(",", ": ")),
                    file=manifest)
            os.unlink(full_manifest_path)
            os.chmod(real_manifest_path, 0o644)

            md5sums_path = os.path.join(control_dir, "md5sums")
            with open(md5sums_path, "w") as md5sums:
                for path in sorted(self.list_files(root_path)):
                    md5 = hashlib.md5()
                    p = os.path.join(root_path, path)
                    if not os.path.exists(p):
                        continue
                    with open(p, "rb") as f:
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
            package_name = "%s_%s_%s.click" % (
                self.name, self.epochless_version, self.architecture)
            package_path = os.path.join(dest_dir, package_name)
            self._pack(temp_dir, control_dir, root_path, package_path)
            return package_path


class ClickSourceBuilder(ClickBuilderBase):

    def __init__(self):
        super(ClickSourceBuilder, self).__init__()
        # From @Dpkg::Source::Package::tar_ignore_default_pattern.
        # (more in ClickBuilderBase)
        self._ignore_patterns += [
            "*.a",
            ".be",
            ".deps",
            "*.la",
            "*.o",
            "*.so",
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
