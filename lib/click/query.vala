/* Copyright (C) 2013, 2014 Canonical Ltd.
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

/* Query information about installed Click packages.  */

namespace Click {

public errordomain QueryError {
	/**
	 * A path could not be canonicalised.
	 */
	PATH,
	/**
	 * No package directory was found.
	 */
	NO_PACKAGE_DIR
}

public string
find_package_directory (string path) throws QueryError
{
	/* We require realpath (path, NULL) to be available. */
	var dir = Posix.realpath (path);
	if (dir == null)
		throw new QueryError.PATH
			("Failed to canonicalize %s: %s",
			 path, strerror (errno));

	do {
		var info_dir = Path.build_filename (dir, ".click", "info");
		if (FileUtils.test (info_dir, FileTest.IS_DIR))
			return dir;
		if (dir == ".")
			break;
		var new_dir = Path.get_dirname (dir);
		if (new_dir == dir)
			break;
		dir = new_dir;
	} while (dir != null);

	throw new QueryError.NO_PACKAGE_DIR
		("No package directory found for %s", path);
}

}
