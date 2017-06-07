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

"""Basic support for writing ar archive files.

We do things this way so that Click packages can be created with minimal
dependencies (e.g. on non-Ubuntu systems).  No read support is needed, since
Click packages are always installed on systems that have dpkg.

Some method names and general approach come from the tarfile module in
Python's standard library; details of the format come from dpkg.
"""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'ArFile',
    ]

import os
import shutil
import time


class ArFile:
    def __init__(self, name=None, mode="w", fileobj=None):
        if mode != "w":
            raise ValueError("only mode 'w' is supported")
        self.mode = mode
        self.real_mode = "wb"

        if fileobj:
            if name is None and hasattr(fileobj, "name"):
                name = fileobj.name
            if hasattr(fileobj, "mode"):
                if fileobj.mode != "wb":
                    raise ValueError("fileobj must be opened with mode='wb'")
                self._mode = fileobj.mode
            self.opened_fileobj = False
        else:
            fileobj = open(name, self.real_mode)
            self.opened_fileobj = True
        self.name = name
        self.fileobj = fileobj
        self.closed = False

    def close(self):
        if self.opened_fileobj:
            self.fileobj.close()
        self.closed = True

    def _check(self):
        if self.closed:
            raise IOError("ArFile %s is closed" % self.name)

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *args):
        self.close()

    def add_magic(self):
        self.fileobj.write(b"!<arch>\n")

    def add_header(self, name, size):
        if len(name) > 15:
            raise ValueError("ar member name '%s' length too long" % name)
        if size > 9999999999:
            raise ValueError("ar member size %d too large" % size)
        header = ("%-16s%-12u0     0     100644  %-10d`\n" % (
            name, int(time.time()), size)).encode()
        assert len(header) == 60  # sizeof(struct ar_hdr)
        self.fileobj.write(header)

    def add_data(self, name, data):
        size = len(data)
        self.add_header(name, size)
        self.fileobj.write(data)
        if size & 1:
            self.fileobj.write(b"\n")  # padding

    def add_file(self, name, path):
        with open(path, "rb") as fobj:
            size = os.fstat(fobj.fileno()).st_size
            self.add_header(name, size)
            shutil.copyfileobj(fobj, self.fileobj)
        if size & 1:
            self.fileobj.write(b"\n")  # padding
