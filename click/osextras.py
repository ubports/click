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

"""Extra OS-level utility functions."""

__all__ = [
    'ensuredir',
    'find_on_path',
    'unlink_force',
    ]


import errno
import os

try:
    # Python 3.3
    from shutil import which
    def find_on_path(command):
        # http://bugs.python.org/issue17012
        path = os.environ.get('PATH', os.pathsep)
        return which(command, path=os.environ.get('PATH', path)) is not None
except ImportError:
    # Python 2
    def find_on_path(command):
        """Is command on the executable search path?"""
        if 'PATH' not in os.environ:
            return False
        path = os.environ['PATH']
        for element in path.split(os.pathsep):
            if not element:
                continue
            filename = os.path.join(element, command)
            if os.path.isfile(filename) and os.access(filename, os.X_OK):
                return True
        return False


def ensuredir(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory)


def listdir_force(directory):
    try:
        return os.listdir(directory)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return []
        raise


def unlink_force(path):
    """Unlink path, without worrying about whether it exists."""
    try:
        os.unlink(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def symlink_force(source, link_name):
    """Create symlink link_name -> source, even if link_name exists."""
    unlink_force(link_name)
    os.symlink(source, link_name)
