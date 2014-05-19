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

"""Unit tests for click.install."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'TestClickInstaller',
    ]


from contextlib import contextmanager
import hashlib
import json
import os
import shutil
import stat
import subprocess

from unittest import skipUnless

from debian.deb822 import Deb822
from gi.repository import Click

from click.build import ClickBuilder
from click.install import (
    ClickInstaller,
    ClickInstallerAuditError,
    ClickInstallerPermissionDenied,
)
from click.preinst import static_preinst
from click.tests.helpers import (
    disable_logging,
    mkfile,
    mock,
    TestCase,
    touch,
)


@contextmanager
def mock_quiet_subprocess_call():
    original_call = subprocess.call

    def side_effect(*args, **kwargs):
        if "TEST_VERBOSE" in os.environ:
            return original_call(*args, **kwargs)
        else:
            with open("/dev/null", "w") as devnull:
                return original_call(
                    *args, stdout=devnull, stderr=devnull, **kwargs)

    with mock.patch("subprocess.call") as mock_call:
        mock_call.side_effect = side_effect
        yield mock_call


class TestClickInstaller(TestCase):
    def setUp(self):
        super(TestClickInstaller, self).setUp()
        self.use_temp_dir()
        self.db = Click.DB()
        self.db.add(self.temp_dir)

    def make_fake_package(self, control_fields=None, manifest=None,
                          control_scripts=None, data_files=None):
        """Build a fake package with given contents."""
        control_fields = {} if control_fields is None else control_fields
        control_scripts = {} if control_scripts is None else control_scripts
        data_files = {} if data_files is None else data_files

        data_dir = os.path.join(self.temp_dir, "fake-package")
        control_dir = os.path.join(self.temp_dir, "DEBIAN")
        with mkfile(os.path.join(control_dir, "control")) as control:
            for key, value in control_fields.items():
                print('%s: %s' % (key.title(), value), file=control)
            print(file=control)
        if manifest is not None:
            with mkfile(os.path.join(control_dir, "manifest")) as f:
                json.dump(manifest, f)
                print(file=f)
        for name, contents in control_scripts.items():
            with mkfile(os.path.join(control_dir, name)) as script:
                script.write(contents)
        Click.ensuredir(data_dir)
        for name, path in data_files.items():
            if path is None:
                touch(os.path.join(data_dir, name))
            elif os.path.isdir(path):
                shutil.copytree(path, os.path.join(data_dir, name))
            else:
                shutil.copy2(path, os.path.join(data_dir, name))
        package_path = '%s.click' % data_dir
        ClickBuilder()._pack(
            self.temp_dir, control_dir, data_dir, package_path)
        return package_path

    def test_audit_no_click_version(self):
        path = self.make_fake_package()
        self.assertRaisesRegex(
            ClickInstallerAuditError, "No Click-Version field",
            ClickInstaller(self.db).audit, path)

    def test_audit_bad_click_version(self):
        path = self.make_fake_package(control_fields={"Click-Version": "|"})
        self.assertRaises(ValueError, ClickInstaller(self.db).audit, path)

    def test_audit_new_click_version(self):
        path = self.make_fake_package(control_fields={"Click-Version": "999"})
        self.assertRaisesRegex(
            ClickInstallerAuditError,
            "Click-Version: 999 newer than maximum supported version .*",
            ClickInstaller(self.db).audit, path)

    def test_audit_forbids_depends(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={
                    "Click-Version": "0.2",
                    "Depends": "libc6",
                })
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            self.assertRaisesRegex(
                ClickInstallerAuditError,
                "Depends field is forbidden in Click packages",
                ClickInstaller(self.db).audit, path)

    def test_audit_forbids_maintscript(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                control_scripts={
                    "preinst": "#! /bin/sh\n",
                    "postinst": "#! /bin/sh\n",
                })
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            self.assertRaisesRegex(
                ClickInstallerAuditError,
                r"Maintainer scripts are forbidden in Click packages "
                r"\(found: postinst preinst\)",
                ClickInstaller(self.db).audit, path)

    def test_audit_requires_manifest(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                control_scripts={"preinst": static_preinst})
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            self.assertRaisesRegex(
                ClickInstallerAuditError, "Package has no manifest",
                ClickInstaller(self.db).audit, path)

    def test_audit_invalid_manifest_json(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                control_scripts={"manifest": "{", "preinst": static_preinst})
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            self.assertRaises(ValueError, ClickInstaller(self.db).audit, path)

    def test_audit_no_name(self):
        path = self.make_fake_package(
            control_fields={"Click-Version": "0.2"},
            manifest={})
        self.assertRaisesRegex(
            ClickInstallerAuditError, 'No "name" entry in manifest',
            ClickInstaller(self.db).audit, path)

    def test_audit_name_bad_character(self):
        path = self.make_fake_package(
            control_fields={"Click-Version": "0.2"},
            manifest={"name": "../evil"})
        self.assertRaisesRegex(
            ClickInstallerAuditError,
            'Invalid character "/" in "name" entry: ../evil',
            ClickInstaller(self.db).audit, path)

    def test_audit_no_version(self):
        path = self.make_fake_package(
            control_fields={"Click-Version": "0.2"},
            manifest={"name": "test-package"})
        self.assertRaisesRegex(
            ClickInstallerAuditError, 'No "version" entry in manifest',
            ClickInstaller(self.db).audit, path)

    def test_audit_no_framework(self):
        path = self.make_fake_package(
            control_fields={"Click-Version": "0.2"},
            manifest={"name": "test-package", "version": "1.0"},
            control_scripts={"preinst": static_preinst})
        self.assertRaisesRegex(
            ClickInstallerAuditError, 'No "framework" entry in manifest',
            ClickInstaller(self.db).audit, path)

    def test_audit_missing_framework(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "missing",
                },
                control_scripts={"preinst": static_preinst})
            self._setup_frameworks(preloads, frameworks=["present"])
            self.assertRaisesRegex(
                ClickInstallerAuditError,
                'Framework "missing" not present on system.*',
                ClickInstaller(self.db).audit, path)

    @disable_logging
    def test_audit_missing_framework_force(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "missing",
                })
            self._setup_frameworks(preloads, frameworks=["present"])
            ClickInstaller(self.db, True).audit(path)

    def test_audit_passes_correct_package(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst})
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            installer = ClickInstaller(self.db)
            self.assertEqual(("test-package", "1.0"), installer.audit(path))

    def test_audit_multiple_frameworks(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.4"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework":
                        "ubuntu-sdk-14.04-basic, ubuntu-sdk-14.04-webapps",
                },
                control_scripts={"preinst": static_preinst})
            installer = ClickInstaller(self.db)
            self._setup_frameworks(preloads, frameworks=["dummy"])
            self.assertRaisesRegex(
                ClickInstallerAuditError,
                'Frameworks "ubuntu-sdk-14.04-basic", '
                '"ubuntu-sdk-14.04-webapps" not present on system.*',
                installer.audit, path)
            self._setup_frameworks(
                preloads, frameworks=["dummy", "ubuntu-sdk-14.04-basic"])
            self.assertRaisesRegex(
                ClickInstallerAuditError,
                'Framework "ubuntu-sdk-14.04-webapps" not present on '
                'system.*',
                installer.audit, path)
            self._setup_frameworks(
                preloads, frameworks=[
                    "dummy", "ubuntu-sdk-14.04-basic",
                    "ubuntu-sdk-14.04-webapps",
                    ])
            self.assertEqual(("test-package", "1.0"), installer.audit(path))

    def test_audit_broken_md5sums(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={
                    "preinst": static_preinst,
                    "md5sums": "%s  foo" % ("0" * 32),
                },
                data_files={"foo": None})
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer = ClickInstaller(self.db)
                self.assertRaises(
                    subprocess.CalledProcessError, installer.audit,
                    path, slow=True)

    def test_audit_matching_md5sums(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            data_path = os.path.join(self.temp_dir, "foo")
            with mkfile(data_path) as data:
                print("test", file=data)
            with open(data_path, "rb") as data:
                data_md5sum = hashlib.md5(data.read()).hexdigest()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={
                    "preinst": static_preinst,
                    "md5sums": "%s  foo" % data_md5sum,
                },
                data_files={"foo": data_path})
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer = ClickInstaller(self.db)
                self.assertEqual(
                    ("test-package", "1.0"), installer.audit(path, slow=True))

    def test_no_write_permission(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={"Click-Version": "0.2"},
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst})
            write_mask = ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            installer = ClickInstaller(self.db)
            temp_dir_mode = os.stat(self.temp_dir).st_mode
            try:
                os.chmod(self.temp_dir, temp_dir_mode & write_mask)
                self.assertRaises(
                    ClickInstallerPermissionDenied, installer.install, path)
            finally:
                os.chmod(self.temp_dir, temp_dir_mode)

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    @mock.patch("gi.repository.Click.package_install_hooks")
    def test_install(self, mock_package_install_hooks):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.0",
                    "Architecture": "all",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst},
                data_files={"foo": None})
            root = os.path.join(self.temp_dir, "root")
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer.install(path)
            self.assertCountEqual([".click", "test-package"], os.listdir(root))
            package_dir = os.path.join(root, "test-package")
            self.assertCountEqual(["1.0", "current"], os.listdir(package_dir))
            inst_dir = os.path.join(package_dir, "current")
            self.assertTrue(os.path.islink(inst_dir))
            self.assertEqual("1.0", os.readlink(inst_dir))
            self.assertCountEqual([".click", "foo"], os.listdir(inst_dir))
            status_path = os.path.join(inst_dir, ".click", "status")
            with open(status_path) as status_file:
                # .readlines() avoids the need for a python-apt backport to
                # Ubuntu 12.04 LTS.
                status = list(Deb822.iter_paragraphs(status_file.readlines()))
            self.assertEqual(1, len(status))
            self.assertEqual({
                "Package": "test-package",
                "Status": "install ok installed",
                "Version": "1.0",
                "Architecture": "all",
                "Maintainer": "Foo Bar <foo@example.org>",
                "Description": "test",
                "Click-Version": "0.2",
            }, status[0])
            mock_package_install_hooks.assert_called_once_with(
                db, "test-package", None, "1.0", user_name=None)

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    def test_sandbox(self):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            original_call = subprocess.call

            def call_side_effect(*args, **kwargs):
                if "TEST_VERBOSE" in os.environ:
                    return original_call(
                        ["touch", os.path.join(self.temp_dir, "sentinel")],
                        **kwargs)
                else:
                    with open("/dev/null", "w") as devnull:
                        return original_call(
                            ["touch", os.path.join(self.temp_dir, "sentinel")],
                            stdout=devnull, stderr=devnull, **kwargs)

            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.0",
                    "Architecture": "all",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.0",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst},
                data_files={"foo": None})
            root = os.path.join(self.temp_dir, "root")
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock.patch("subprocess.call") as mock_call:
                mock_call.side_effect = call_side_effect
                self.assertRaises(
                    subprocess.CalledProcessError, installer.install, path)
            self.assertFalse(
                os.path.exists(os.path.join(self.temp_dir, "sentinel")))

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    @mock.patch("gi.repository.Click.package_install_hooks")
    def test_upgrade(self, mock_package_install_hooks):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            os.environ["TEST_QUIET"] = "1"
            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.1",
                    "Architecture": "all",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.1",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst},
                data_files={"foo": None})
            root = os.path.join(self.temp_dir, "root")
            package_dir = os.path.join(root, "test-package")
            inst_dir = os.path.join(package_dir, "current")
            os.makedirs(os.path.join(package_dir, "1.0"))
            os.symlink("1.0", inst_dir)
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer.install(path)
            self.assertCountEqual([".click", "test-package"], os.listdir(root))
            self.assertCountEqual(["1.1", "current"], os.listdir(package_dir))
            self.assertTrue(os.path.islink(inst_dir))
            self.assertEqual("1.1", os.readlink(inst_dir))
            self.assertCountEqual([".click", "foo"], os.listdir(inst_dir))
            status_path = os.path.join(inst_dir, ".click", "status")
            with open(status_path) as status_file:
                # .readlines() avoids the need for a python-apt backport to
                # Ubuntu 12.04 LTS.
                status = list(Deb822.iter_paragraphs(status_file.readlines()))
            self.assertEqual(1, len(status))
            self.assertEqual({
                "Package": "test-package",
                "Status": "install ok installed",
                "Version": "1.1",
                "Architecture": "all",
                "Maintainer": "Foo Bar <foo@example.org>",
                "Description": "test",
                "Click-Version": "0.2",
            }, status[0])
            mock_package_install_hooks.assert_called_once_with(
                db, "test-package", "1.0", "1.1", user_name=None)

    def _get_mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    @mock.patch("gi.repository.Click.package_install_hooks")
    def test_world_readable(self, mock_package_install_hooks):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            owner_only_file = os.path.join(self.temp_dir, "owner-only-file")
            touch(owner_only_file)
            os.chmod(owner_only_file, stat.S_IRUSR | stat.S_IWUSR)
            owner_only_dir = os.path.join(self.temp_dir, "owner-only-dir")
            os.mkdir(owner_only_dir, stat.S_IRWXU)
            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.1",
                    "Architecture": "all",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.1",
                    "framework": "ubuntu-sdk-13.10",
                },
                control_scripts={"preinst": static_preinst},
                data_files={
                    "world-readable-file": owner_only_file,
                    "world-readable-dir": owner_only_dir,
                })
            root = os.path.join(self.temp_dir, "root")
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer.install(path)
            inst_dir = os.path.join(root, "test-package", "current")
            self.assertEqual(
                stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH,
                self._get_mode(os.path.join(inst_dir, "world-readable-file")))
            self.assertEqual(
                stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP |
                stat.S_IROTH | stat.S_IXOTH,
                self._get_mode(os.path.join(inst_dir, "world-readable-dir")))

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    @mock.patch("gi.repository.Click.package_install_hooks")
    @mock.patch("click.install.ClickInstaller._dpkg_architecture")
    def test_single_architecture(self, mock_dpkg_architecture,
                                 mock_package_install_hooks):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            mock_dpkg_architecture.return_value = "armhf"
            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.1",
                    "Architecture": "armhf",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.1",
                    "framework": "ubuntu-sdk-13.10",
                    "architecture": "armhf",
                },
                control_scripts={"preinst": static_preinst})
            root = os.path.join(self.temp_dir, "root")
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer.install(path)
            self.assertTrue(
                os.path.exists(os.path.join(root, "test-package", "current")))

    @skipUnless(
        os.path.exists(ClickInstaller(None)._preload_path()),
        "preload bits not built; installing packages will fail")
    @mock.patch("gi.repository.Click.package_install_hooks")
    @mock.patch("click.install.ClickInstaller._dpkg_architecture")
    def test_multiple_architectures(self, mock_dpkg_architecture,
                                    mock_package_install_hooks):
        with self.run_in_subprocess(
                "click_get_frameworks_dir") as (enter, preloads):
            enter()
            mock_dpkg_architecture.return_value = "armhf"
            path = self.make_fake_package(
                control_fields={
                    "Package": "test-package",
                    "Version": "1.1",
                    "Architecture": "multi",
                    "Maintainer": "Foo Bar <foo@example.org>",
                    "Description": "test",
                    "Click-Version": "0.2",
                },
                manifest={
                    "name": "test-package",
                    "version": "1.1",
                    "framework": "ubuntu-sdk-13.10",
                    "architecture": ["armhf", "i386"],
                },
                control_scripts={"preinst": static_preinst})
            root = os.path.join(self.temp_dir, "root")
            db = Click.DB()
            db.add(root)
            installer = ClickInstaller(db)
            self._setup_frameworks(preloads, frameworks=["ubuntu-sdk-13.10"])
            with mock_quiet_subprocess_call():
                installer.install(path)
            self.assertTrue(
                os.path.exists(os.path.join(root, "test-package", "current")))

    @disable_logging
    def test_reinstall_preinstalled(self):
        # Attempting to reinstall a preinstalled version shouldn't actually
        # reinstall it in an overlay database (which would cause
        # irreconcilable confusion about the correct target for system hook
        # symlinks), but should instead simply update the user registration.
        path = self.make_fake_package(
            control_fields={
                "Package": "test-package",
                "Version": "1.1",
                "Architecture": "all",
                "Maintainer": "Foo Bar <foo@example.org>",
                "Description": "test",
                "Click-Version": "0.4",
            },
            manifest={
                "name": "test-package",
                "version": "1.1",
                "framework": "ubuntu-sdk-13.10",
            },
            control_scripts={"preinst": static_preinst})
        underlay = os.path.join(self.temp_dir, "underlay")
        overlay = os.path.join(self.temp_dir, "overlay")
        db = Click.DB()
        db.add(underlay)
        installer = ClickInstaller(db, True)
        with mock_quiet_subprocess_call():
            installer.install(path, all_users=True)
        underlay_unpacked = os.path.join(underlay, "test-package", "1.1")
        self.assertTrue(os.path.exists(underlay_unpacked))
        all_link = os.path.join(
            underlay, ".click", "users", "@all", "test-package")
        self.assertTrue(os.path.islink(all_link))
        self.assertEqual(underlay_unpacked, os.readlink(all_link))
        db.add(overlay)
        registry = Click.User.for_user(db, "test-user")
        registry.remove("test-package")
        user_link = os.path.join(
            overlay, ".click", "users", "test-user", "test-package")
        self.assertTrue(os.path.islink(user_link))
        self.assertEqual("@hidden", os.readlink(user_link))
        installer = ClickInstaller(db, True)
        with mock_quiet_subprocess_call():
            installer.install(path, user="test-user")
        overlay_unpacked = os.path.join(overlay, "test-package", "1.1")
        self.assertFalse(os.path.exists(overlay_unpacked))
        self.assertEqual("1.1", registry.get_version("test-package"))
