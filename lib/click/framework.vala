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

/* Click frameworks. */

namespace Click {

public errordomain FrameworkError {
	/**
	 * Requested framework does not exist.
	 */
	NO_SUCH_FRAMEWORK,
	/**
	 * Missing hook field.
	 */
	MISSING_FIELD
}

public class Framework : Object {
	public string name { get; construct; }

	private Gee.Map<string, string> fields;

	private
	Framework (string name)
	{
		Object (name: name);
	}

	/**
	 * Framework.open:
	 * @name: The name of the framework to open.
	 *
	 * Returns: (transfer full): A newly-allocated #Click.Framework.
	 *
	 * Since: 0.4.18
	 */
	public static Framework
	open (string name) throws FrameworkError
	{
		var path = Path.build_filename
			(get_frameworks_dir (), @"$name.framework");
		try {
			var framework = new Framework (name);
			framework.fields = parse_deb822_file (path);
			return framework;
		} catch (Error e) {
			throw new FrameworkError.NO_SUCH_FRAMEWORK
				("No click framework '%s' installed", name);
		}
	}

	/**
	 * has_framework:
	 * @name: A framework name.
	 *
	 * Returns: True if a framework by this name exists, otherwise false.
	 *
	 * Since: 0.4.18
	 */
	public static bool
	has_framework (string name)
	{
		var path = Path.build_filename
			(get_frameworks_dir (), @"$name.framework");
		return exists (path);
	}

	/**
	 * get_frameworks:
	 *
	 * Returns: (element-type ClickFramework) (transfer full): A #List
	 * of all #Click.Framework instances installed on the system.
	 *
	 * Since: 0.4.18
	 */
	public static List<Framework>
	get_frameworks ()
	{
		var ret = new List<Framework> ();
		Click.Dir dir;
		try {
			dir = Click.Dir.open (get_frameworks_dir ());
		} catch (FileError e) {
			return ret;
		}
		foreach (var entry in dir) {
			if (! entry.has_suffix (".framework"))
				continue;
			try {
				ret.prepend (open (entry[0:-10]));
			} catch (Error e) {
				continue;
			}
		}
		ret.reverse ();
		return ret;
	}

	/**
	 * get_fields:
	 *
	 * Returns: A list of field names defined by this framework.
	 *
	 * Since: 0.4.18
	 */
	public List<string>
	get_fields ()
	{
		var ret = new List<string> ();
		foreach (var key in fields.keys)
			ret.prepend (key);
		ret.reverse ();
		return ret;
	}

	public string
	get_field (string key) throws FrameworkError
	{
		string value = fields[key.down ()];
		if (value == null)
			throw new FrameworkError.MISSING_FIELD
				("Framework '%s' has no field named '%s'",
				 name, key);
		return value;
	}

	public string?
	get_base_name ()
	{
		return fields["base-name"];
	}

	public string?
	get_base_version ()
	{
		return fields["base-version"];
	}
}

}
