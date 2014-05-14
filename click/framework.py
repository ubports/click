# Copyright (C) 2014 Canonical Ltd.
# Author: Michael Vogt <michael.vogt@canonical.com>

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

"""Pure python click framework handling support."""

import logging
import os
import re

try:
    import apt_pkg
except:
    pass

import click.paths


class ClickFrameworkInvalid(Exception):
    pass


# FIXME: use native lib if available
#from gi.repository import Click
#click_framework_get_base_version = Click.framework_get_base_version
#click_framework_has_framework = Click.has_framework


# python version of the vala parse_deb822_file()
def parse_deb822_file(filename):
    data = {}
    with open(filename) as f:
        for line in f:
            line = line.strip()
            # from deb822.vala
            field_re_posix = r'^([^:[:space:]]+)[[:space:]]*:[[:space:]]'\
                       '([^[:space:]].*?)[[:space:]]*$'
            # python does not do posix char classes
            field_re = field_re_posix.replace("[:space:]", "\s")
            blank_re_posix = r'^[[:space:]]*$'
            blank_re = blank_re_posix.replace("[:space:]", "\s")
            if re.match(blank_re, line):
                break
            match = re.match(field_re, line)
            if match and match.group(1) and match.group(2):
                data[match.group(1).lower()] = match.group(2)
    return data


# python version of vala get_frameworks_dir
def get_frameworks_dir():
    return click.paths.frameworks_dir


def get_framework_path(framework_name):
    framework_path = os.path.join(
        get_frameworks_dir(), framework_name+".framework")
    return framework_path


# python version of the vala click_framework_get_base_version()
def click_framework_get_base_version(framework_name):
    deb822 = parse_deb822_file(get_framework_path(framework_name))
    return deb822.get("base-version", None)


# python version of the vala click_framework_has_framework
def click_framework_has_framework(framework_name):
    return os.path.exists(get_framework_path(framework_name))


def validate_framework(framework_string, ignore_missing_frameworks=False):
    try:
        apt_pkg
    except NameError:
        logging.warning("No apt_pkg module, skipping validate_framework")
        return

    try:
        parsed_framework = apt_pkg.parse_depends(framework_string)
    except ValueError:
        raise ClickFrameworkInvalid(
            'Could not parse framework "%s"' % framework_string)

    framework_base_versions = set()
    missing_frameworks = []
    for or_dep in parsed_framework:
        if len(or_dep) > 1:
            raise ClickFrameworkInvalid(
                'Alternative dependencies in framework "%s" not yet '
                'allowed' % framework_string)
        if or_dep[0][1] or or_dep[0][2]:
            raise ClickFrameworkInvalid(
                'Version relationship in framework "%s" not yet allowed' %
                framework_string)
        # now verify that different base versions are not mixed
        framework_name = or_dep[0][0]
        if not click_framework_has_framework(framework_name):
            missing_frameworks.append(framework_name)
            continue
        framework_base_version = click_framework_get_base_version(
                framework_name)
        framework_base_versions.add(framework_base_version)

    if not ignore_missing_frameworks:
        if len(missing_frameworks) > 1:
            raise ClickFrameworkInvalid(
                'Frameworks %s not present on system (use '
                '--force-missing-framework option to override)' %
                ", ".join('"%s"' % f for f in missing_frameworks))
        elif missing_frameworks:
            raise ClickFrameworkInvalid(
                'Framework "%s" not present on system (use '
                '--force-missing-framework option to override)' %
                missing_frameworks[0])
    else:
        if len(missing_frameworks) > 1:
            logging.warning("Ignoring missing frameworks %s" % (
                ", ".join('"%s"' % f for f in missing_frameworks)))
        elif missing_frameworks:
            logging.warning('Ignoring missing framework "%s"' % (
                missing_frameworks[0]))

    if len(framework_base_versions) > 1:
        raise ClickFrameworkInvalid(
            'Multiple frameworks with different base versions are not '
            'allowed. Found: {0}'.format(framework_base_versions))
