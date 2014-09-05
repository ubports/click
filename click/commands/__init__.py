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

"""click commands."""

import importlib


all_commands = (
    "build",
    "buildsource",
    "chroot",
    "contents",
    "desktophook",
    "framework",
    "hook",
    "info",
    "install",
    "list",
    "pkgdir",
    "register",
    "unregister",
    "verify",
    )


hidden_commands = (
    "desktophook",
    )


def load_command(command):
    return importlib.import_module("click.commands.%s" % command)


def help_text():
    lines = []
    for command in all_commands:
        if command in hidden_commands:
            continue
        mod = load_command(command)
        lines.append("  %-21s %s" % (command, mod.__doc__.splitlines()[0]))
    return "\n".join(lines)
