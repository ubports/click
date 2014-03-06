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

/* Extra OS-level utility functions.  */

namespace Click {

/**
 * find_on_path:
 * @command: A command name.
 *
 * Returns: True if the command is on the executable search path, otherwise
 * false.
 */
public bool
find_on_path (string command)
{
	unowned string? path = Environment.get_variable ("PATH");
	if (path == null)
		return false;

	var elements = path.split(":");
	foreach (var element in elements) {
		if (element == "")
			continue;
		var filename = Path.build_filename (element, command);
		if (FileUtils.test (filename, FileTest.IS_REGULAR) &&
		    FileUtils.test (filename, FileTest.IS_EXECUTABLE))
			return true;
	}

	return false;
}

/**
 * ensuredir:
 * @directory: A path.
 *
 * If @directory does not already exist, create it and its parents as
 * needed.
 */
public void
ensuredir (string directory) throws FileError
{
	if (FileUtils.test (directory, FileTest.IS_DIR))
		return;
	if (DirUtils.create_with_parents (directory, 0777) < 0) {
		var code = FileUtils.error_from_errno (errno);
		var quark = Quark.from_string ("g-file-error-quark");
		var err = new Error (quark, code,
				     "ensuredir %s failed: %s",
				     directory, strerror (errno));
		throw (FileError) err;
	}
}

/**
 * unlink_force:
 * @path: A path to unlink.
 *
 * Unlink path, without worrying about whether it exists.  Errors other than
 * %ENOENT will set the provided error location.
 */
public void
unlink_force (string path) throws FileError
{
	if (FileUtils.unlink (path) < 0 && errno != Posix.ENOENT) {
		var code = FileUtils.error_from_errno (errno);
		var quark = Quark.from_string ("g-file-error-quark");
		var err = new Error (quark, code,
				     "unlink %s failed: %s",
				     path, strerror (errno));
		throw (FileError) err;
	}
}

/**
 * symlink_force:
 * @target: The intended target of the symbolic link.
 * @link_name: A path where the symbolic link should be created.
 *
 * Create a symlink link_name -> target, even if link_name exists.
 */
public void
symlink_force (string target, string link_name) throws FileError
{
	unlink_force (link_name);
	/* This produces a harmless warning when compiling C code generated
	 * by valac 0.22.1:
	 *   https://bugzilla.gnome.org/show_bug.cgi?id=725151
	 */
	if (FileUtils.symlink (target, link_name) < 0) {
		var code = FileUtils.error_from_errno (errno);
		var quark = Quark.from_string ("g-file-error-quark");
		var err = new Error (quark, code,
				     "symlink %s -> %s failed: %s",
				     link_name, target, strerror (errno));
		throw (FileError) err;
	}
}

/**
 * click_get_umask:
 *
 * Returns: The current umask.
 */
public int
get_umask ()
{
	var mask = Posix.umask (0);
	Posix.umask (mask);
	return (int) mask;
}

public class Dir : Object {
	private SList<string> entries;
	private unowned SList<string> cur;

	private Dir ()
	{
	}

	/**
	 * open:
	 * @path: The path to the directory to open.
	 * @flags: For future use; currently must be set to 0.
	 *
	 * Like GLib.Dir.open(), but ignores %ENOENT.
	 */
	public static Dir?
	open (string path, uint _flags = 0) throws FileError
	{
		Dir dir = new Dir ();
		dir.entries = new SList<string> ();

		GLib.Dir real_dir;
		try {
			real_dir = GLib.Dir.open (path, _flags);
			string? name;
			while ((name = real_dir.read_name ()) != null)
				dir.entries.prepend (name);
			dir.entries.sort (strcmp);
		} catch (FileError e) {
			if (! (e is FileError.NOENT))
				throw e;
		}

		dir.cur = dir.entries;
		return dir;
	}

	/**
	 * read_name:
	 *
	 * Like GLib.Dir.read_name(), but returns entries in sorted order.
	 */
	public unowned string?
	read_name ()
	{
		if (cur == null)
			return null;
		unowned string name = cur.data;
		cur = cur.next;
		return name;
	}

	internal class Iterator : Object {
		private Dir dir;

		public Iterator (Dir dir) {
			this.dir = dir;
		}

		public unowned string?
		next_value ()
		{
			return dir.read_name ();
		}
	}

	internal Iterator
	iterator ()
	{
		return new Iterator (this);
	}
}

private bool
exists (string path)
{
	return FileUtils.test (path, FileTest.EXISTS);
}

private bool
is_symlink (string path)
{
	return FileUtils.test (path, FileTest.IS_SYMLINK);
}

}
