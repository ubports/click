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

/* Click databases.  */

namespace Click {

public errordomain DatabaseError {
	/**
	 * A package/version does not exist.
	 */
	DOES_NOT_EXIST,
	/**
	 * Failure to remove package.
	 */
	REMOVE,
	/**
	 * Failure to ensure correct ownership of database files.
	 */
	ENSURE_OWNERSHIP,
	/**
	 * Package manifest cannot be parsed.
	 */
	BAD_MANIFEST,
	/**
	 * No database available for the given request
	 */
	INVALID
}

private string? app_pid_command = null;

private unowned string? get_app_pid_command ()
{
	if (app_pid_command == null) {
		if (find_on_path ("ubuntu-app-pid"))
			app_pid_command = "ubuntu-app-pid";
		else if (find_on_path ("upstart-app-pid"))
			app_pid_command = "upstart-app-pid";
		else
			app_pid_command = "";
	}

	if (app_pid_command == "")
		return null;
	else
		return app_pid_command;
}

public class InstalledPackage : Object, Gee.Hashable<InstalledPackage> {
	public string package { get; construct; }
	public string version { get; construct; }
	public string path { get; construct; }
	public bool writeable { get; construct; default = true; }

	public InstalledPackage (string package, string version, string path,
				 bool writeable = true)
	{
		Object (package: package, version: version, path: path,
			writeable: writeable);
	}

	public uint
	hash ()
	{
		return package.hash () ^ version.hash () ^ path.hash () ^
		       (writeable ? 1 : 0);
	}

	public bool
	equal_to (InstalledPackage obj)
	{
		return package == obj.package && version == obj.version &&
		       path == obj.path && writeable == obj.writeable;
	}
}

public class SingleDB : Object {
	public string root { get; construct; }
	public DB master_db { private get; construct; }

	public
	SingleDB (string root, DB master_db)
	{
		Object (root: root, master_db: master_db);
	}

	private bool
	show_messages ()
	{
		return Environment.get_variable ("TEST_QUIET") == null;
	}

	/**
	 * get_path:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: The path to this version of this package.
	 */
	public string
	get_path (string package, string version) throws DatabaseError
	{
		var try_path = Path.build_filename (root, package, version);
		if (exists (try_path))
			return try_path;
		else
			throw new DatabaseError.DOES_NOT_EXIST
				("%s %s does not exist in %s",
				 package, version, root);
	}

	/**
	 * has_package_version:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: True if this version of this package is unpacked in this
	 * database, otherwise false.
	 *
	 * Since: 0.4.18
	 */
	public bool
	has_package_version (string package, string version)
	{
		try {
			get_path (package, version);
			return true;
		} catch (DatabaseError e) {
			return false;
		}
	}

	/**
	 * get_packages:
	 * @all_versions: If true, return all versions, not just current ones.
	 *
	 * Returns: A list of #InstalledPackage instances corresponding to
	 * package versions in only this database.
	 */
	public List<InstalledPackage>
	get_packages (bool all_versions = false) throws Error
	{
		var ret = new List<InstalledPackage> ();

		foreach (var package in Click.Dir.open (root)) {
			if (package == ".click")
				continue;
			if (all_versions) {
				var package_path =
					Path.build_filename (root, package);
				if (! is_dir (package_path))
					continue;
				foreach (var version in Click.Dir.open
						(package_path)) {
					var version_path = Path.build_filename
						(package_path, version);
					if (is_symlink (version_path) ||
					    ! is_dir (version_path))
						continue;
					ret.prepend(new InstalledPackage
						(package, version,
						 version_path));
				}
			} else {
				var current_path = Path.build_filename
					(root, package, "current");
				if (! is_symlink (current_path))
					continue;
				var version = FileUtils.read_link
					(current_path);
				if (! ("/" in version))
					ret.prepend(new InstalledPackage
						(package, version,
						 current_path));
			}
		}

		ret.reverse ();
		return ret;
	}

	/**
	 * get_manifest:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: A #Json.Object containing the manifest of this version
	 * of this package.  The manifest may include additional dynamic
	 * keys (starting with an underscore) corresponding to dynamic
	 * properties of installed packages.
	 *
	 * Since: 0.4.18
	 */
	public Json.Object
	get_manifest (string package, string version) throws DatabaseError
	{
		/* Extract the raw manifest from the file system. */
		var path = get_path (package, version);
		var manifest_path = Path.build_filename
			(path, ".click", "info", @"$package.manifest");
		var parser = new Json.Parser ();
		try {
			parser.load_from_file (manifest_path);
		} catch (Error e) {
			throw new DatabaseError.BAD_MANIFEST
				("Failed to parse manifest in %s: %s",
				 manifest_path, e.message);
		}
		var node = parser.get_root ();
		if (node.get_node_type () != Json.NodeType.OBJECT)
			throw new DatabaseError.BAD_MANIFEST
				("Manifest in %s is not a JSON object",
				 manifest_path);
		var manifest = node.dup_object ();

		/* Set up dynamic keys. */
		var to_remove = new List<string> ();
		foreach (var name in manifest.get_members ()) {
			if (name.has_prefix ("_"))
				to_remove.prepend (name);
		}
		foreach (var name in to_remove)
			manifest.remove_member (name);
		manifest.set_string_member ("_directory", path);

		return manifest;
	}

	/**
	 * get_manifest_as_string:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: A JSON string containing the serialised manifest of this
	 * version of this package.  The manifest may include additional
	 * dynamic keys (starting with an underscore) corresponding to
	 * dynamic properties of installed packages.
	 * This interface may be useful for clients with their own JSON
	 * parsing tools that produce representations more convenient for
	 * them.
	 *
	 * Since: 0.4.21
	 */
	public string
	get_manifest_as_string (string package, string version)
	throws DatabaseError
	{
		var manifest = get_manifest (package, version);
		var node = new Json.Node (Json.NodeType.OBJECT);
		node.set_object (manifest);
		var generator = new Json.Generator ();
		generator.set_root (node);
		return generator.to_data (null);
	}

	/*
	 * app_running:
	 * @package: A package name.
	 * @app_name: An application name.
	 * @version: A version string.
	 *
	 * Returns: True if @app_name from version @version of @package is
	 * known to be running, otherwise false.
	 */
	public bool
	app_running (string package, string app_name, string version)
	{
		string[] command = {
			get_app_pid_command (),
			@"$(package)_$(app_name)_$(version)"
		};
		assert (command[0] != null);
		try {
			int exit_status;
			Process.spawn_sync
				(null, command, null,
				 SpawnFlags.SEARCH_PATH |
				 SpawnFlags.STDOUT_TO_DEV_NULL,
				 null, null, null, out exit_status);
			return Process.check_exit_status (exit_status);
		} catch (Error e) {
			return false;
		}
	}

	/*
	 * any_app_running:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: True if any application from version @version of
	 * @package is known to be running, otherwise false.
	 */
	public bool
	any_app_running (string package, string version) throws DatabaseError
	{
		if (get_app_pid_command () == null)
			return false;

		var manifest_path = Path.build_filename
			(get_path (package, version), ".click", "info",
			 @"$package.manifest");
		var parser = new Json.Parser ();
		try {
			parser.load_from_file (manifest_path);
			var manifest = parser.get_root ().get_object ();
			if (! manifest.has_member ("hooks"))
				return false;
			var hooks = manifest.get_object_member ("hooks");
			foreach (unowned string app_name in
					hooks.get_members ()) {
				if (app_running (package, app_name, version))
					return true;
			}
		} catch (Error e) {
		}
		return false;
	}

	private void
	remove_unless_running (string package, string version) throws Error
	{
		if (any_app_running (package, version))
			return;

		var version_path = get_path (package, version);
		if (show_messages ())
			message ("Removing %s", version_path);
		package_remove_hooks (master_db, package, version);
		/* In Python, we used shutil.rmtree(version_path,
		 * ignore_errors=True), but GLib doesn't have an obvious
		 * equivalent.  I could write a recursive version with GLib,
		 * but this isn't performance-critical and it isn't worth
		 * the hassle for now, so just call out to "rm -rf" instead.
		 */
		string[] argv = { "rm", "-rf", version_path };
		int exit_status;
		Process.spawn_sync (null, argv, null, SpawnFlags.SEARCH_PATH,
				    null, null, null, out exit_status);
		Process.check_exit_status (exit_status);

		var package_path = Path.build_filename (root, package);
		var current_path = Path.build_filename
			(package_path, "current");
		if (is_symlink (current_path) &&
		    FileUtils.read_link (current_path) == version) {
			if (FileUtils.unlink (current_path) < 0)
				throw new DatabaseError.REMOVE
					("unlink %s failed: %s",
					 current_path, strerror (errno));
			/* TODO: Perhaps we should relink current to the
			 * latest remaining version.  However, that requires
			 * version comparison, and it's not clear whether
			 * it's worth it given that current is mostly
			 * superseded by user registration.
			 */
		}
		if (DirUtils.remove (package_path) < 0) {
			if (errno != Posix.ENOTEMPTY &&
			    errno != Posix.EEXIST)
				throw new DatabaseError.REMOVE
					("rmdir %s failed: %s",
					 package_path, strerror (errno));
		}
	}

	/**
	 * maybe_remove:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Remove a package version if it is not in use.
	 *
	 * "In use" may mean registered for another user, or running.  In
	 * either case, we do nothing.  We will already have removed at
	 * least one registration by this point, so if no registrations are
	 * left but it is running, then gc will be able to come along later
	 * and clean things out.
	 */
	public void
	maybe_remove (string package, string version) throws Error
	{
		var users_db = new Users (master_db);
		foreach (var user_name in users_db.get_user_names ()) {
			var user_db = users_db.get_user (user_name);
			string reg_version;
			try {
				reg_version = user_db.get_version (package);
			} catch (UserError e) {
				continue;
			}
			if (reg_version == version) {
				/* In use. */
				return;
			}
		}

		remove_unless_running (package, version);
	}

	/**
	 * gc:
	 *
	 * Remove package versions that have no user registrations and that
	 * are not running.
	 *
	 * This is rather like maybe_remove, but is suitable for bulk use,
	 * since it only needs to scan the database once rather than once
	 * per package.
	 *
	 * For historical reasons, we don't count @gcinuse as a real user
	 * registration, and remove any such registrations we find.  We can
	 * drop this once we no longer care about upgrading versions from
	 * before this change to something more current in a single step.
	 */
	public void
	gc () throws Error
	{
		var users_db = new Users (master_db);
		var user_reg = new Gee.HashMultiMap<string, string> ();
		foreach (var user_name in users_db.get_user_names ()) {
			var user_db = users_db.get_user (user_name);
			foreach (var package in user_db.get_package_names ()) {
				var version = user_db.get_version (package);
				if (version == "current")
					continue;
				/* Odd multimap syntax; this should really
				 * be more like foo[package] += version.
				 */
				if (! user_db.is_gc_in_use)
					user_reg[package] = version;
			}
		}

		var gc_in_use_user_db = new User.for_gc_in_use (master_db);
		foreach (var package in Click.Dir.open (root)) {
			if (package == ".click")
				continue;
			var package_path = Path.build_filename (root, package);
			if (! is_dir (package_path))
				continue;
			foreach (var version in Click.Dir.open
					(package_path)) {
				if (version == "current")
					continue;
				if (version in user_reg[package])
					/* In use. */
					continue;
				if (gc_in_use_user_db.has_package_name
						(package))
					gc_in_use_user_db.remove (package);
				remove_unless_running (package, version);
			}
		}
	}

	private delegate void WalkFunc (string dirpath, string[] dirnames,
					string[] filenames) throws Error;

	/**
	 * walk:
	 *
	 * An reduced emulation of Python's os.walk.
	 */
	private void
	walk (string top, WalkFunc func) throws Error
	{
		string[] dirs = {};
		string[] nondirs = {};
		foreach (var name in Click.Dir.open (top)) {
			var path = Path.build_filename (top, name);
			if (is_dir (path))
				dirs += name;
			else
				nondirs += name;
		}
		func (top, dirs, nondirs);
		foreach (var name in dirs) {
			var path = Path.build_filename (top, name);
			if (! is_symlink (path))
				walk (path, func);
		}
	}

	private delegate void ClickpkgForeachFunc (string path)
		throws DatabaseError;

	/**
	 * foreach_clickpkg_path:
	 *
	 * Call a delegate for each path which should be owned by clickpkg.
	 */
	private void
	foreach_clickpkg_path (ClickpkgForeachFunc func) throws Error
	{
		if (exists (root))
			func (root);
		foreach (var package in Click.Dir.open (root)) {
			var path = Path.build_filename (root, package);
			if (package == ".click") {
				func (path);
				var log_path = Path.build_filename
					(path, "log");
				if (exists (log_path))
					func (log_path);
				var users_path = Path.build_filename
					(path, "users");
				if (exists (users_path))
					func (users_path);
			} else {
				walk (path, (dp, dns, fns) => {
					func (dp);
					foreach (var dn in dns) {
						var dnp = Path.build_filename
							(dp, dn);
						if (is_symlink (dnp))
							func (dnp);
					}
					foreach (var fn in fns) {
						var fnp = Path.build_filename
							(dp, fn);
						func (fnp);
					}
				});
			}
		}
	}

	/**
	 * ensure_ownership:
	 *
	 * Ensure correct ownership of files in the database.
	 *
	 * On a system that is upgraded by delivering a new system image
	 * rather than by package upgrades, it is possible for the clickpkg
	 * UID to change.  The overlay database must then be adjusted to
	 * account for this.
	 */
	public void
	ensure_ownership () throws Error
	{
		errno = 0;
		unowned Posix.Passwd? pw = Posix.getpwnam ("clickpkg");
		if (pw == null)
			throw new DatabaseError.ENSURE_OWNERSHIP
				("Cannot get password file entry for " +
				 "clickpkg: %s", strerror (errno));
		Posix.Stat st;
		if (Posix.stat (root, out st) < 0)
			return;
		if (st.st_uid == pw.pw_uid && st.st_gid == pw.pw_gid)
			return;
		foreach_clickpkg_path ((path) => {
			if (Posix.chown (path, pw.pw_uid, pw.pw_gid) < 0)
				throw new DatabaseError.ENSURE_OWNERSHIP
					("Cannot set ownership of %s: %s",
					 path, strerror (errno));
		});
	}
}

public class DB : Object {
	private Gee.ArrayList<SingleDB> db = new Gee.ArrayList<SingleDB> ();

	public DB () {}

	public void
	read (string? db_dir = null) throws FileError
	{
		string real_db_dir = (db_dir == null) ? get_db_dir () : db_dir;

		foreach (var name in Click.Dir.open (real_db_dir)) {
			if (! name.has_suffix (".conf"))
				continue;
			var path = Path.build_filename (real_db_dir, name);
			var config = new KeyFile ();
			string root;
			try {
				config.load_from_file
					(path, KeyFileFlags.NONE);
				root = config.get_string
					("Click Database", "root");
			} catch (Error e) {
				warning ("%s", e.message);
				continue;
			}
			assert (root != null);
			add (root);
		}
	}

	public int size { get { return db.size; } }

	public new SingleDB
	@get (int index) throws DatabaseError
	{
		if (index >= db.size)
			throw new DatabaseError.INVALID
                ("invalid index %i for db of size %i", index, db.size);
		return db.get (index);
	}

	public new void
	add (string root)
	{
		db.add (new SingleDB (root, this));
	}

	/**
	 * overlay:
	 *
	 * The directory where changes should be written.
	 */
	public string overlay 
	{ 
		get {
			if (db.size == 0)
				return "";
			else
				return db.last ().root;
		}
	}

	/**
	 * get_path:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: The path to this version of this package.
	 */
	public string
	get_path (string package, string version) throws DatabaseError
	{
		foreach (var single_db in db) {
			try {
				return single_db.get_path (package, version);
			} catch (DatabaseError e) {
			}
		}
		throw new DatabaseError.DOES_NOT_EXIST
			("%s %s does not exist in any database",
			 package, version);
	}

	/**
	 * has_package_version:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: True if this version of this package is unpacked,
	 * otherwise false.
	 */
	public bool
	has_package_version (string package, string version)
	{
		try {
			get_path (package, version);
			return true;
		} catch (DatabaseError e) {
			return false;
		}
	}

	/**
	 * get_packages:
	 * @all_versions: If true, return all versions, not just current ones.
	 *
	 * Returns: A list of #InstalledPackage instances corresponding to
	 * package versions in all databases.
	 */
	public List<InstalledPackage>
	get_packages (bool all_versions = false) throws Error
	{
		var ret = new List<InstalledPackage> ();
		var seen = new Gee.HashSet<string> ();
		var writeable = true;
		for (int i = db.size - 1; i >= 0; --i) {
			var child_packages = db[i].get_packages (all_versions);
			foreach (var pkg in child_packages) {
				string seen_id;
				if (all_versions)
					seen_id = (
						pkg.package + "_" +
						pkg.version);
				else
					seen_id = pkg.package.dup ();

				if (! (seen_id in seen)) {
					ret.prepend(new InstalledPackage
						(pkg.package, pkg.version,
						 pkg.path, writeable));
					seen.add (seen_id);
				}
			}
			writeable = false;
		}

		ret.reverse ();
		return ret;
	}

	/**
	 * get_manifest:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: A #Json.Object containing the manifest of this version
	 * of this package.
	 *
	 * Since: 0.4.18
	 */
	public Json.Object
	get_manifest (string package, string version) throws DatabaseError
	{
		foreach (var single_db in db) {
			try {
				return single_db.get_manifest
					(package, version);
			} catch (DatabaseError e) {
				if (e is DatabaseError.BAD_MANIFEST)
					throw e;
			}
		}
		throw new DatabaseError.DOES_NOT_EXIST
			("%s %s does not exist in any database",
			 package, version);
	}

	/**
	 * get_manifest_as_string:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Returns: A JSON string containing the serialised manifest of this
	 * version of this package.
	 * This interface may be useful for clients with their own JSON
	 * parsing tools that produce representations more convenient for
	 * them.
	 *
	 * Since: 0.4.21
	 */
	public string
	get_manifest_as_string (string package, string version)
	throws DatabaseError
	{
		var manifest = get_manifest (package, version);
		var node = new Json.Node (Json.NodeType.OBJECT);
		node.set_object (manifest);
		var generator = new Json.Generator ();
		generator.set_root (node);
		return generator.to_data (null);
	}

	/**
	 * get_manifests:
	 * @all_versions: If true, return manifests for all versions, not
	 * just current ones.
	 *
	 * Returns: A #Json.Array containing manifests of all packages in
	 * this database.  The manifest may include additional dynamic keys
	 * (starting with an underscore) corresponding to dynamic properties
	 * of installed packages.
	 *
	 * Since: 0.4.18
	 */
	public Json.Array
	get_manifests (bool all_versions = false) throws Error
	{
		var ret = new Json.Array ();
		foreach (var inst in get_packages (all_versions)) {
			Json.Object obj;
			try {
				obj = get_manifest
					(inst.package, inst.version);
			} catch (DatabaseError e) {
				warning ("%s", e.message);
				continue;
			}
			/* This should really be a boolean, but it was
			 * mistakenly made an int when the "_removable" key
			 * was first created.  We may change this in future.
			 */
			obj.set_int_member ("_removable",
					    inst.writeable ? 1 : 0);
			ret.add_object_element (obj);
		}
		return ret;
	}

	/**
	 * get_manifests_as_string:
	 * @all_versions: If true, return manifests for all versions, not
	 * just current ones.
	 *
	 * Returns: A JSON string containing a serialised array of manifests
	 * of all packages in this database.  The manifest may include
	 * additional dynamic keys (starting with an underscore)
	 * corresponding to dynamic properties of installed packages.
	 * This interface may be useful for clients with their own JSON
	 * parsing tools that produce representations more convenient for
	 * them.
	 *
	 * Since: 0.4.21
	 */
	public string
	get_manifests_as_string (bool all_versions = false) throws Error
	{
		var manifests = get_manifests (all_versions);
		var node = new Json.Node (Json.NodeType.ARRAY);
		node.set_array (manifests);
		var generator = new Json.Generator ();
		generator.set_root (node);
		return generator.to_data (null);
	}

	private void
	ensure_db () throws Error
	{
		if (db.size == 0)
			throw new DatabaseError.INVALID
                ("no database loaded");
	}

	public void
	maybe_remove (string package, string version) throws Error
	{
		ensure_db();
		db.last ().maybe_remove (package, version);
	}

	public void
	gc () throws Error
	{
		ensure_db();
		db.last ().gc ();
	}

	public void
	ensure_ownership () throws Error
	{
		ensure_db();
		db.last ().ensure_ownership ();
	}
}

}
