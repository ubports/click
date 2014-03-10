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

"""Helper functions to turn json-glib objects into Python objects."""

from __future__ import print_function

__metaclass__ = type
__all__ = [
    'ClickJsonError',
    'json_array_to_python',
    'json_node_to_python',
    'json_object_to_python',
    ]


from gi.repository import Json


class ClickJsonError(Exception):
    pass


def json_array_to_python(array):
    return [json_node_to_python(element) for element in array.get_elements()]


def json_object_to_python(obj):
    ret = {}
    for name in obj.get_members():
        ret[name] = json_node_to_python(obj.get_member(name))
    return ret


def json_node_to_python(node):
    node_type = node.get_node_type()
    if node_type == Json.NodeType.ARRAY:
        return json_array_to_python(node.get_array())
    elif node_type == Json.NodeType.OBJECT:
        return json_object_to_python(node.get_object())
    elif node_type == Json.NodeType.NULL:
        return None
    elif node_type == Json.NodeType.VALUE:
        return node.get_value()
    else:
        raise ClickJsonError(
            "Unknown JSON node type \"%s\"" % node_type.value_nick)
