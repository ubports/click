# Copyright (C) 2014 Canonical Ltd.
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

"""A collection of variously hacky ctypes definitions for use with gimock."""

import ctypes

from click.tests.config import (
    STAT_OFFSET_GID,
    STAT_OFFSET_UID,
    STAT64_OFFSET_GID,
    STAT64_OFFSET_UID,
    )


class Passwd(ctypes.Structure):
    _fields_ = [
        ("pw_name", ctypes.c_char_p),
        ("pw_passwd", ctypes.c_char_p),
        ("pw_uid", ctypes.c_uint32),
        ("pw_gid", ctypes.c_uint32),
        ("pw_gecos", ctypes.c_char_p),
        ("pw_dir", ctypes.c_char_p),
        ("pw_shell", ctypes.c_char_p),
        ]


# TODO: This is pretty awful.  The layout of "struct stat" is complicated
# enough that we have to use offsetof() in configure to pick out the fields
# we care about.  Fortunately, we only care about a couple of fields, and
# since this is an output parameter it doesn't matter if our structure is
# too short (if we cared about this then we could use AC_CHECK_SIZEOF to
# figure it out).
class Stat(ctypes.Structure):
    _pack_ = 1
    _fields_ = []
    _fields_.append(
        ("pad0", ctypes.c_ubyte * min(STAT_OFFSET_UID, STAT_OFFSET_GID)))
    if STAT_OFFSET_UID < STAT_OFFSET_GID:
        _fields_.append(("st_uid", ctypes.c_uint32))
        pad = (STAT_OFFSET_GID - STAT_OFFSET_UID -
               ctypes.sizeof(ctypes.c_uint32))
        assert pad >= 0
        if pad > 0:
            _fields_.append(("pad1", ctypes.c_ubyte * pad))
        _fields_.append(("st_gid", ctypes.c_uint32))
    else:
        _fields_.append(("st_gid", ctypes.c_uint32))
        pad = (STAT_OFFSET_UID - STAT_OFFSET_GID -
               ctypes.sizeof(ctypes.c_uint32))
        assert pad >= 0
        if pad > 0:
            _fields_.append(("pad1", ctypes.c_ubyte * pad))
        _fields_.append(("st_uid", ctypes.c_uint32))


class Stat64(ctypes.Structure):
    _pack_ = 1
    _fields_ = []
    _fields_.append(
        ("pad0", ctypes.c_ubyte * min(STAT64_OFFSET_UID, STAT64_OFFSET_GID)))
    if STAT64_OFFSET_UID < STAT64_OFFSET_GID:
        _fields_.append(("st_uid", ctypes.c_uint32))
        pad = (STAT64_OFFSET_GID - STAT64_OFFSET_UID -
               ctypes.sizeof(ctypes.c_uint32))
        assert pad >= 0
        if pad > 0:
            _fields_.append(("pad1", ctypes.c_ubyte * pad))
        _fields_.append(("st_gid", ctypes.c_uint32))
    else:
        _fields_.append(("st_gid", ctypes.c_uint32))
        pad = (STAT64_OFFSET_UID - STAT64_OFFSET_GID -
               ctypes.sizeof(ctypes.c_uint32))
        assert pad >= 0
        if pad > 0:
            _fields_.append(("pad1", ctypes.c_ubyte * pad))
        _fields_.append(("st_uid", ctypes.c_uint32))
