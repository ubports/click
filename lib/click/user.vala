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

/* Registry of user-installed Click packages.
 * 
 * Click packages are installed into per-package/version directories, so it
 * is quite feasible for more than one version of a given package to be
 * installed at once, allowing per-user installations; for instance, one
 * user of a tablet may be uncomfortable with granting some new permission
 * to an app, but another may be just fine with it.  To make this useful, we
 * also need a registry of which users have which versions of each package
 * installed.
 * 
 * We might have chosen to use a proper database.  However, a major goal of
 * Click packages is extreme resilience; we must never get into a situation
 * where some previous error in package installation or removal makes it
 * hard for the user to install or remove other packages.  Furthermore, the
 * simpler application execution can be the better.  So, instead, we use
 * just about the simplest "database" format imaginable: a directory of
 * symlinks per user.
 */

namespace Click {

/* Pseudo-usernames selected to be invalid as a real username, and alluding
 * to group syntaxes used in other systems.
 */
private const string ALL_USERS = "@all";
private const string GC_IN_USE_USER = "@gcinuse";

/* Pseudo-versions.  In this case the @ doesn't allude to group syntaxes,
 * but since @ is conveniently invalid in version numbers we stick to the
 * same prefix used for pseudo-usernames.
 */
private const string HIDDEN_VERSION = "@hidden";

public errordomain UserError {
	/**
	 * Failure to get password file entry.
	 */
	GETPWNAM,
	/**
	 * Failure to create database directory.
	 */
	CREATE_DB,
	/**
	 * Failure to set ownership of database directory.
	 */
	CHOWN_DB,
	/**
	 * Requested user does not exist.
	 */
	NO_SUCH_USER,
	/**
	 * Failure to drop privileges.
	 */
	DROP_PRIVS,
	/**
	 * Failure to regain privileges.
	 */
	REGAIN_PRIVS,
	/**
	 * Requested package is hidden.
	 */
	HIDDEN_PACKAGE,
	/**
	 * Requested package does not exist.
	 */
	NO_SUCH_PACKAGE,
	/**
	 * Failure to rename file.
	 */
	RENAME
}

private string
db_top (string root)
{
	/* This is deliberately outside any user's home directory so that it
	 * can safely be iterated etc. as root.
	 */
	return Path.build_filename (root, ".click", "users");
}

private string
db_for_user (string root, string user)
{
	return Path.build_filename (db_top (root), user);
}

private void
try_create (string path) throws UserError
{
	if (DirUtils.create (path, 0777) < 0)
		throw new UserError.CREATE_DB
			("Cannot create database directory %s: %s",
			 path, strerror (errno));
}

private class CachedPasswd : Object {
	public Posix.uid_t uid;
	public Posix.gid_t gid;

	public
	CachedPasswd (Posix.uid_t uid, Posix.gid_t gid)
	{
		this.uid = uid;
		this.gid = gid;
	}
}

private void
try_chown (string path, CachedPasswd pw) throws UserError
{
	if (Posix.chown (path, pw.uid, pw.gid) < 0)
		throw new UserError.CHOWN_DB
			("Cannot set ownership of database directory %s: %s",
			 path, strerror (errno));
}

public class Users : Object {
	public DB db { private get; construct; }
	private CachedPasswd? click_pw;

	public Users (DB db)
	{
		Object (db: db);
		click_pw = null;
	}

	/**
	 * get_click_pw:
	 *
	 * Returns: The password file entry for the `clickpkg` user.
	 */
	private CachedPasswd
	get_click_pw () throws UserError
	{
		if (click_pw == null) {
			errno = 0;
			unowned Posix.Passwd pw = Posix.getpwnam ("clickpkg");
			if (pw == null)
				throw new UserError.GETPWNAM
					("Cannot get password file entry " +
					 "for clickpkg: %s", strerror (errno));
			click_pw = new CachedPasswd (pw.pw_uid, pw.pw_gid);
		}
		return click_pw;
	}

	internal void
	ensure_db () throws UserError
	{
		var create = new List<string> ();

		/* Only modify the last database. */
		var try_path = db_top (db.overlay);
		while (! exists (try_path)) {
			create.prepend (try_path);
			try_path = Path.get_dirname (try_path);
		}

		foreach (var path in create) {
			try_create (path);
			if (Posix.geteuid () == 0)
				try_chown (path, get_click_pw ());
		}
	}

	/**
	 * get_user_names:
	 *
	 * Returns: A list of user names with registrations.
	 */
	public List<string>
	get_user_names () throws Error
	{
		var entries = new List<string> ();
		var seen = new Gee.HashSet<string> ();
		foreach (var single_db in db) {
			var users_db = db_top (single_db.root);
			foreach (var entry in Click.Dir.open (users_db)) {
				if (entry in seen)
					continue;
				var path = Path.build_filename (users_db,
								entry);
				if (is_dir (path)) {
					seen.add (entry.dup ());
					entries.prepend (entry.dup ());
				}
			}
		}
		entries.reverse ();
		return entries;
	}

	/**
	 * get_user:
	 * @user_name: A user name.
	 *
	 * Returns: (transfer full): A new #ClickUser instance for @user.
	 */
	public User
	get_user (string user_name) throws Error
	{
		foreach (var single_db in db) {
			var path = db_for_user (single_db.root, user_name);
			if (is_dir (path))
				/* We only require the user path to exist in
				 * any database; it doesn't matter which.
				 */
				return new User.for_user (db, user_name);
		}
		throw new UserError.NO_SUCH_USER(
			"User %s does not exist in any database", user_name);
	}
}

public class User : Object {
	public DB db { private get; construct; }
	public string name { private get; construct; }

	private Users? users;
	private CachedPasswd? user_pw;
	private int dropped_privileges_count;
	private Posix.mode_t? old_umask;

	private User (DB? db, string? name = null) throws FileError {
		DB real_db;
		string real_name;
		if (db != null)
			real_db = db;
		else {
			real_db = new DB ();
			real_db.read ();
		}
		if (name != null)
			real_name = name;
		else
			real_name = Environment.get_user_name ().dup ();
		Object (db: real_db, name: real_name);
		users = null;
		user_pw = null;
		dropped_privileges_count = 0;
		old_umask = null;
	}

	public User.for_user (DB? db, string? name = null) throws FileError {
		this (db, name);
	}

	public User.for_all_users (DB? db) throws FileError {
		this (db, ALL_USERS);
	}

	public User.for_gc_in_use (DB? db) throws FileError {
		this (db, GC_IN_USE_USER);
	}

	/**
	 * True if and only if this user is a pseudo-user.
	 */
	public bool is_pseudo_user { get { return name.has_prefix ("@"); } }

	/**
	 * True if and only if this user is the pseudo-user indicating that
	 * a registration was in use at the time of package removal.
	 */
	public bool is_gc_in_use { get { return name == GC_IN_USE_USER; } }

	/**
	 * get_user_pw:
	 *
	 * Returns: The password file entry for this user.
	 */
	private CachedPasswd
	get_user_pw () throws UserError
	{
		assert (! is_pseudo_user);

		if (user_pw == null) {
			errno = 0;
			unowned Posix.Passwd pw = Posix.getpwnam (name);
			if (pw == null)
				throw new UserError.GETPWNAM
				     ("Cannot get password file entry for " +
				      "%s: %s", name, strerror (errno));
			user_pw = new CachedPasswd (pw.pw_uid, pw.pw_gid);
		}
		return user_pw;
	}

	/**
	 * get_overlay_db:
	 *
	 * Returns: The path to the overlay database for this user, i.e. the
	 * path where new packages will be installed.
	 */
	public string
	get_overlay_db ()
	{
		return db_for_user (db.overlay, name);
	}

	private void
	ensure_db () throws UserError
	{
		if (users == null)
			users = new Users (db);
		users.ensure_db ();
		var path = get_overlay_db ();
		if (! exists (path)) {
			try_create (path);
			if (Posix.geteuid () == 0 && ! is_pseudo_user)
				try_chown (path, get_user_pw ());
		}
	}

	/* Note on privilege handling:
	 * We can normally get away without dropping privilege when reading,
	 * but some filesystems are strict about how much they let root work
	 * with user files (e.g. NFS root_squash).  It is better to play it
	 * safe and drop privileges for any operations on the user's
	 * database.
	 */

	private void
	priv_drop_failure (string name) throws UserError
	{
		throw new UserError.DROP_PRIVS
			("Cannot drop privileges (%s): %s",
			 name, strerror (errno));
	}

	internal void
	drop_privileges () throws UserError
	{
		if (dropped_privileges_count == 0 &&
		    Posix.getuid () == 0 && ! is_pseudo_user) {
			/* We don't bother with setgroups here; we only need
			 * the user/group of created filesystem nodes to be
			 * correct.
			 */
			var pw = get_user_pw ();
			if (PosixExtra.setegid (pw.gid) < 0)
				priv_drop_failure ("setegid");
			if (PosixExtra.seteuid (pw.uid) < 0)
				priv_drop_failure ("seteuid");
			old_umask = Posix.umask (get_umask () | Posix.S_IWOTH);
		}

		++dropped_privileges_count;
	}

	private void
	priv_regain_failure (string name)
	{
		/* It is too dangerous to carry on from this point, even if
		 * the caller has an exception handler.
		 */
		error ("Cannot regain privileges (%s): %s",
		       name, strerror (errno));
	}

	internal void
	regain_privileges ()
	{
		--dropped_privileges_count;

		if (dropped_privileges_count == 0 &&
		    Posix.getuid () == 0 && ! is_pseudo_user) {
			if (old_umask != null)
				Posix.umask (old_umask);
			if (PosixExtra.seteuid (0) < 0)
				priv_regain_failure ("seteuid");
			if (PosixExtra.setegid (0) < 0)
				priv_regain_failure ("setegid");
		}
	}

	private bool
	is_valid_link (string path)
	{
		if (! is_symlink (path))
			return false;

		try {
			var target = FileUtils.read_link (path);
			return ! target.has_prefix ("@");
		} catch (FileError e) {
			return false;
		}
	}

	private List<string>
	get_package_names_dropped () throws Error
	{
		var entries = new List<string> ();
		var hidden = new Gee.HashSet<string> ();
		for (int i = db.size - 1; i >= 0; --i) {
			var user_db = db_for_user (db[i].root, name);
			foreach (var entry in Click.Dir.open (user_db)) {
				if (entries.find_custom (entry, strcmp)
					!= null ||
				    entry in hidden)
					continue;
				var path = Path.build_filename (user_db, entry);
				if (is_valid_link (path))
					entries.prepend (entry.dup ());
				else if (is_symlink (path))
					hidden.add (entry.dup ());
			}

			if (name != ALL_USERS) {
				var all_users_db = db_for_user (db[i].root,
								ALL_USERS);
				foreach (var entry in Click.Dir.open
						(all_users_db)) {
					if (entries.find_custom (entry, strcmp)
						!= null ||
					    entry in hidden)
						continue;
					var path = Path.build_filename
						(all_users_db, entry);
					if (is_valid_link (path))
						entries.prepend (entry.dup ());
					else if (is_symlink (path))
						hidden.add (entry.dup ());
				}
			}
		}
		entries.reverse ();
		return entries;
	}

	/**
	 * get_package_names:
	 *
	 * Returns: (transfer full): A list of package names installed for
	 * this user.
	 */
	public List<string>
	get_package_names () throws Error
	{
		drop_privileges ();
		try {
			return get_package_names_dropped ();
		} finally {
			regain_privileges ();
		}
	}

	/**
	 * has_package_name:
	 * @package: A package name.
	 *
	 * Returns: True if this user has a version of @package registered,
	 * otherwise false.
	 */
	public bool
	has_package_name (string package)
	{
		try {
			get_version (package);
			return true;
		} catch (UserError e) {
			return false;
		}
	}

	/**
	 * get_version:
	 * @package: A package name.
	 *
	 * Returns: The version of @package registered for this user.
	 */
	public string
	get_version (string package) throws UserError
	{
		for (int i = db.size - 1; i >= 0; --i) {
			var user_db = db_for_user (db[i].root, name);
			var path = Path.build_filename (user_db, package);
			drop_privileges ();
			try {
				if (is_valid_link (path)) {
					try {
						var target =
							FileUtils.read_link
							(path);
						return Path.get_basename
							(target);
					} catch (FileError e) {
					}
				} else if (is_symlink (path))
					throw new UserError.HIDDEN_PACKAGE
						("%s is hidden for user %s",
						 package, name);
			} finally {
				regain_privileges ();
			}

			var all_users_db = db_for_user (db[i].root, ALL_USERS);
			path = Path.build_filename (all_users_db, package);
			if (is_valid_link (path)) {
				try {
					var target = FileUtils.read_link
						(path);
					return Path.get_basename (target);
				} catch (FileError e) {
				}
			} else if (is_symlink (path))
				throw new UserError.HIDDEN_PACKAGE
					("%s is hidden for all users",
					 package);
		}

		throw new UserError.NO_SUCH_PACKAGE
			("%s does not exist in any database for user %s",
			 package, name);
	}

	/**
	 * raw_set_version:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Set the version of @package to @version, without running any
	 * hooks.  Must be run with dropped privileges.
	 */
	internal void
	raw_set_version (string package, string version) throws Error
	{
		assert (dropped_privileges_count > 0);
		var user_db = get_overlay_db ();
		var path = Path.build_filename (user_db, package);
		var new_path = Path.build_filename (user_db, @".$package.new");
		var target = db.get_path (package, version);
		var done = false;
		if (is_valid_link (path)) {
			unlink_force (path);
			try {
				if (get_version (package) == version)
					done = true;
			} catch (UserError e) {
			}
		}
		if (done)
			return;
		symlink_force (target, new_path);
		if (FileUtils.rename (new_path, path) < 0)
			throw new UserError.RENAME
				("rename %s -> %s failed: %s",
				 new_path, path, strerror (errno));
	}

	/**
	 * set_version:
	 * @package: A package name.
	 * @version: A version string.
	 *
	 * Register version @version of @package for this user.
	 */
	public void
	set_version (string package, string version) throws Error
	{
		/* Only modify the last database. */
		ensure_db ();
		string? old_version = null;
		try {
			old_version = get_version (package);
		} catch (UserError e) {
		}
		drop_privileges ();
		try {
			raw_set_version (package, version);
		} finally {
			regain_privileges ();
		}
		if (! is_pseudo_user)
			package_install_hooks (db, package,
					       old_version, version, name);
	}

	/**
	 * remove:
	 * @package: A package name.
	 *
	 * Remove this user's registration of @package.
	 */
	public void
	remove (string package) throws Error
	{
		/* Only modify the last database. */
		var user_db = get_overlay_db ();
		var path = Path.build_filename (user_db, package);
		string old_version;
		if (is_valid_link (path)) {
			var target = FileUtils.read_link (path);
			old_version = Path.get_basename (target);
			drop_privileges ();
			try {
				unlink_force (path);
			} finally {
				regain_privileges ();
			}
		} else {
			try {
				old_version = get_version (package);
			} catch (UserError e) {
				throw new UserError.NO_SUCH_PACKAGE
					("%s does not exist in any database " +
					 "for user %s", package, name);
			}
			ensure_db ();
			drop_privileges ();
			try {
				symlink_force (HIDDEN_VERSION, path);
			} finally {
				regain_privileges ();
			}
		}
		if (! is_pseudo_user)
			package_remove_hooks (db, package, old_version, name);
	}

	/**
	 * get_path:
	 * @package: A package name.
	 *
	 * Returns: The path at which @package is registered for this user.
	 */
	public string
	get_path (string package) throws UserError
	{
		for (int i = db.size - 1; i >= 0; --i) {
			var user_db = db_for_user (db[i].root, name);
			var path = Path.build_filename (user_db, package);
			if (is_valid_link (path))
				return path;
			else if (is_symlink (path))
				throw new UserError.HIDDEN_PACKAGE
					("%s is hidden for user %s",
					 package, name);

			var all_users_db = db_for_user (db[i].root, ALL_USERS);
			path = Path.build_filename (all_users_db, package);
			if (is_valid_link (path))
				return path;
			else if (is_symlink (path))
				throw new UserError.HIDDEN_PACKAGE
					("%s is hidden for all users",
					 package);
		}

		throw new UserError.NO_SUCH_PACKAGE
			("%s does not exist in any database for user %s",
			 package, name);
	}

	/**
	 * get_manifest:
	 * @package: A package name.
	 *
	 * Returns: A #Json.Object containing a package's manifest.
	 *
	 * Since: 0.4.18
	 */
	public Json.Object
	get_manifest (string package) throws Error
	{
		var obj = db.get_manifest (package, get_version (package));
		/* Adjust _directory to point to the user registration path. */
		obj.set_string_member ("_directory", get_path (package));
		/* This should really be a boolean, but it was mistakenly
		 * made an int when the "_removable" key was first created.
		 * We may change this in future.
		 */
		obj.set_int_member ("_removable",
				    is_removable (package) ? 1 : 0);
		return obj;
	}

	/**
	 * get_manifest_as_string:
	 * @package: A package name.
	 *
	 * Returns: A JSON string containing a package's serialised
	 * manifest.
	 * This interface may be useful for clients with their own JSON
	 * parsing tools that produce representations more convenient for
	 * them.
	 *
	 * Since: 0.4.21
	 */
	public string
	get_manifest_as_string (string package) throws Error
	{
		var manifest = get_manifest (package);
		var node = new Json.Node (Json.NodeType.OBJECT);
		node.set_object (manifest);
		var generator = new Json.Generator ();
		generator.set_root (node);
		return generator.to_data (null);
	}

	/**
	 * get_manifests:
	 *
	 * Returns: A #Json.Array containing manifests of all packages
	 * registered for this user.  The manifest may include additional
	 * dynamic keys (starting with an underscore) corresponding to
	 * dynamic properties of installed packages.
	 *
	 * Since: 0.4.18
	 */
	public Json.Array
	get_manifests () throws Error /* API-compatibility */
	{
		var ret = new Json.Array ();
		foreach (var package in get_package_names ()) {
			try {
				ret.add_object_element
					(get_manifest (package));
			} catch (Error e) {
				warning ("%s", e.message);
			}
		}
		return ret;
	}

	/**
	 * get_manifests_as_string:
	 *
	 * Returns: A JSON string containing a serialised array of manifests
	 * of all packages registered for this user.  The manifest may
	 * include additional dynamic keys (starting with an underscore)
	 * corresponding to dynamic properties of installed packages.
	 * This interface may be useful for clients with their own JSON
	 * parsing tools that produce representations more convenient for
	 * them.
	 *
	 * Since: 0.4.21
	 */
	public string
	get_manifests_as_string () throws Error /* API-compatibility */
	{
		var manifests = get_manifests ();
		var node = new Json.Node (Json.NodeType.ARRAY);
		node.set_array (manifests);
		var generator = new Json.Generator ();
		generator.set_root (node);
		return generator.to_data (null);
	}

	/**
	 * is_removable:
	 * @package: A package name.
	 *
	 * Returns: True if @package is removable for this user, otherwise
	 * False.
	 */
	public bool
	is_removable (string package)
	{
		var user_db = get_overlay_db ();
		var path = Path.build_filename (user_db, package);
		if (exists (path))
			return true;
		else if (is_symlink (path))
			/* Already hidden. */
			return false;
		var all_users_db = db_for_user (db.overlay, ALL_USERS);
		path = Path.build_filename (all_users_db, package);
		if (is_valid_link (path))
			return true;
		else if (is_symlink (path))
			/* Already hidden. */
			return false;
		if (has_package_name (package))
			/* Not in overlay database, but can be hidden. */
			return true;
		else
			return false;
	}
}

}
