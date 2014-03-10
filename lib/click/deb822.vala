/* Copyright (C) 2014 Canonical Ltd.
 * Author: Colin Watson <cjwatson@ubuntu.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

/* Simple deb822-like file parsing. */

namespace Click {

private Regex? field_re = null;
private Regex? blank_re = null;

/**
 * parse_deb822_file:
 * @path: Path to a file.
 *
 * A very simple deb822-like file parser.
 *
 * Note that this only supports a single paragraph composed only of simple
 * (non-folded/multiline) fields, which is fortunately all we need in Click.
 *
 * Returns: A mapping of field names to values.
 */
private Gee.Map<string, string>
parse_deb822_file (string path) throws Error
{
	if (field_re == null)
		field_re = new Regex
			("^([^:[:space:]]+)[[:space:]]*:[[:space:]]" +
			 "([^[:space:]].*?)[[:space:]]*$");
	if (blank_re == null)
		blank_re = new Regex ("^[[:space:]]*$");

	var ret = new Gee.HashMap<string, string> ();
	var channel = new IOChannel.file (path, "r");
	string line;
	while (channel.read_line (out line, null, null) == IOStatus.NORMAL &&
	       line != null) {
		MatchInfo match_info;

		if (blank_re.match (line))
			break;

		if (field_re.match (line, 0, out match_info)) {
			var key = match_info.fetch (1);
			var value = match_info.fetch (2);
			if (key != null && value != null)
				ret[key.down ()] = value;
		}
	}
	return ret;
}

}
