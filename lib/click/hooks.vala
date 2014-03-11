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

/* Click package hooks.
 *
 * See doc/hooks.rst for the draft specification.
 */

namespace Click {

public errordomain HooksError {
	/**
	 * Requested hook does not exist.
	 */
	NO_SUCH_HOOK,
	/**
	 * Missing hook field.
	 */
	MISSING_FIELD,
	/**
	 * Invalid application name.
	 */
	BAD_APP_NAME,
	/**
	 * Requested user does not exist.
	 */
	NO_SUCH_USER,
	/**
	 * Failure to drop privileges.
	 */
	DROP_PRIVS,
	/**
	 * Not yet implemented.
	 */
	NYI
}

private Json.Object
read_manifest_hooks (DB db, string package, string? version)
	throws DatabaseError
{
	if (version == null)
		return new Json.Object ();
	var parser = new Json.Parser ();
	try {
		var manifest_path = Path.build_filename
			(db.get_path (package, version), ".click", "info",
			 @"$package.manifest");
		parser.load_from_file (manifest_path);
		var manifest = parser.get_root ().get_object ();
		if (! manifest.has_member ("hooks"))
			return new Json.Object ();
		var hooks = manifest.get_object_member ("hooks");
		return hooks.ref ();
	} catch (Error e) {
		return new Json.Object ();
	}
}

private class PreviousEntry : Object, Gee.Hashable<PreviousEntry> {
	public string path { get; construct; }
	public string package { get; construct; }
	public string version { get; construct; }
	public string app_name { get; construct; }

	public
	PreviousEntry (string path, string package, string version,
		       string app_name)
	{
		Object (path: path, package: package, version: version,
			app_name: app_name);
	}

	public uint
	hash ()
	{
		return path.hash () ^ package.hash () ^ version.hash () ^
		       app_name.hash ();
	}

	public bool
	equal_to (PreviousEntry obj)
	{
		return path == obj.path && package == obj.package &&
		       version == obj.version && app_name == obj.app_name;
	}
}

private class UnpackedPackage : Object, Gee.Hashable<UnpackedPackage> {
	public string package { get; construct; }
	public string version { get; construct; }
	public string? user_name { get; construct; }

	public
	UnpackedPackage (string package, string version,
			 string? user_name = null)
	{
		Object (package: package, version: version,
			user_name: user_name);
	}

	public uint
	hash ()
	{
		return package.hash () ^ version.hash () ^
		       (user_name != null ? user_name.hash () : 0);
	}

	public bool
	equal_to (UnpackedPackage obj)
	{
		return package == obj.package && version == obj.version &&
		       user_name == obj.user_name;
	}
}

private class RelevantApp : Object, Gee.Hashable<RelevantApp> {
	public string package { get; construct; }
	public string version { get; construct; }
	public string app_name { get; construct; }
	public string? user_name { get; construct; }
	public string relative_path { get; construct; }

	public
	RelevantApp (string package, string version, string app_name,
		     string? user_name, string relative_path)
	{
		Object (package: package, version: version, app_name: app_name,
			user_name: user_name, relative_path: relative_path);
	}

	public uint
	hash ()
	{
		return package.hash () ^ version.hash () ^ app_name.hash () ^
		       (user_name != null ? user_name.hash () : 0) ^
		       relative_path.hash ();
	}

	public bool
	equal_to (RelevantApp obj)
	{
		return package == obj.package && version == obj.version &&
		       app_name == obj.app_name &&
		       user_name == obj.user_name &&
		       relative_path == obj.relative_path;
	}
}

private class AppHook : Object, Gee.Hashable<AppHook>,
			Gee.Comparable<AppHook> {
	public string app_name { get; construct; }
	public string hook_name { get; construct; }

	public
	AppHook (string app_name, string hook_name)
	{
		Object (app_name: app_name, hook_name: hook_name);
	}

	public uint
	hash ()
	{
		return app_name.hash () ^ hook_name.hash ();
	}

	public bool
	equal_to (AppHook obj)
	{
		return app_name == obj.app_name && hook_name == obj.hook_name;
	}

	public int
	compare_to (AppHook obj)
	{
		var ret = strcmp (app_name, obj.app_name);
		if (ret != 0)
			return ret;
		return strcmp (hook_name, obj.hook_name);
	}
}

private class ParsedPattern : Object {
	public bool is_expansion { get; construct; }
	public string text { get; construct; }

	public
	ParsedPattern (bool is_expansion, string text)
	{
		Object (is_expansion: is_expansion, text: text);
	}
}

private Regex? expansion_re = null;

/**
 * pattern_parse:
 * @format_string: A format string.
 *
 * Parse @format_string into segments.
 *
 * Returns: A list of #ParsedPattern segments.
 */
private Gee.List<ParsedPattern>
pattern_parse (string format_string)
{
	const string EXPANSION = "\\$(?:\\$|{(.*?)})";
	var ret = new Gee.ArrayList<ParsedPattern> ();
	MatchInfo match_info;
	var last_end = 0;

	if (expansion_re == null) {
		try {
			expansion_re = new Regex (EXPANSION);
		} catch (RegexError e) {
			error ("Could not compile regex /%s/: %s",
			       EXPANSION, e.message);
		}
	}

	expansion_re.match (format_string, 0, out match_info);
	while (match_info.matches ()) {
		int start, end;
		var fetched = match_info.fetch_pos (0, out start, out end);
		assert (fetched);
		string? key = null;
		if (start + 2 == end && format_string[start] == '$' &&
		    format_string[start + 1] == '$')
			++start;
		else
			key = match_info.fetch (1);
		if (last_end < start) {
			var segment = format_string.substring
				(last_end, start - last_end);
			ret.add (new ParsedPattern (false, segment));
		}
		if (key != null)
			ret.add (new ParsedPattern (true, key));

		last_end = end;
		try {
			match_info.next ();
		} catch (RegexError e) {
			break;
		}
	}
	if (last_end < format_string.length)
		ret.add (new ParsedPattern
			(false, format_string.substring (last_end)));

	return ret;
}

/**
 * pattern_format:
 * @format_string: A format string.
 * @args: A #GLib.Variant of type "a{sms}", binding keys to values.
 *
 * Apply simple $-expansions to a string.
 *
 * `${key}` is replaced by the value of the `key` argument; `$$` is replaced
 * by `$`.  Any `$` character not followed by `{...}` is preserved intact.
 *
 * Returns: The expanded string.
 */
public string
pattern_format (string format_string, Variant args)
{
	string[] pieces = {};
	foreach (var segment in pattern_parse (format_string)) {
		if (segment.is_expansion) {
			unowned string value;
			if (args.lookup (segment.text, "m&s", out value))
				pieces += value;
		} else
			pieces += segment.text;
	}
	return string.joinv ("", pieces);
}

/**
 * click_pattern_possible_expansion:
 * @s: A string.
 * @format_string: A format string.
 * @args: A #GLib.Variant of type "a{sms}", binding keys to values.
 *
 * Check if @s is a possible $-expansion of @format_string.
 *
 * Entries in @args have the effect of binding some keys to fixed values;
 * unspecified keys may take any value, and will bind greedily to the
 * longest possible string.
 *
 * Returns: If @s is a possible expansion, then this function returns a
 * (possibly empty) dictionary #GLib.Variant mapping all the unspecified
 * keys to their bound values.  Otherwise, it returns null.
 */
public Variant?
pattern_possible_expansion (string s, string format_string, Variant args)
{
	string[] regex_pieces = {};
	string[] group_names = {};
	foreach (var segment in pattern_parse (format_string)) {
		if (segment.is_expansion) {
			unowned string value;
			if (args.lookup (segment.text, "m&s", out value))
				regex_pieces += Regex.escape_string (value);
			else {
				regex_pieces += "(.*)";
				group_names += segment.text;
			}
		} else
			regex_pieces += Regex.escape_string (segment.text);
	}
	var joined = string.joinv ("", regex_pieces);
	Regex compiled;
	try {
		compiled = new Regex ("^" + joined + "$");
	} catch (RegexError e) {
		return null;
	}
	MatchInfo match_info;
	var builder = new VariantBuilder (new VariantType ("a{ss}"));
	if (compiled.match (s, 0, out match_info)) {
		for (int group_i = 0; group_i < group_names.length;
		     ++group_i) {
			var match = match_info.fetch (group_i + 1);
			assert (match != null);
			builder.add ("{ss}", group_names[group_i], match);
		}
		return builder.end ();
	} else
		return null;
}

public class Hook : Object {
	public DB db { private get; construct; }
	public string name { private get; construct; }

	private Gee.Map<string, string> fields;

	private Hook (DB db, string name)
	{
		Object (db: db, name: name);
	}

	/**
	 * Hook.open:
	 * @db: A #Click.DB.
	 * @name: The name of the hook to open.
	 *
	 * Returns: (transfer full): A newly-allocated #Click.Hook.
	 */
	public static Hook
	open (DB db, string name) throws HooksError
	{
		var hook_path = Path.build_filename
			(get_hooks_dir (), @"$name.hook");
		try {
			var hook = new Hook (db, name);
			hook.fields = parse_deb822_file (hook_path);
			return hook;
		} catch (Error e) {
			throw new HooksError.NO_SUCH_HOOK
				("No click hook '%s' installed", name);
		}
	}

	/**
	 * open_all:
	 * @db: A #Click.DB.
	 * @hook_name: (allow-none): A string to match against Hook-Name
	 * fields, or null.
	 *
	 * Returns: (element-type ClickHook) (transfer full): A #List of
	 * #Click.Hook instances whose Hook-Name fields equal the value of
	 * @hook_name.
	 */
	public static List<Hook>
	open_all (DB db, string? hook_name = null) throws FileError
	{
		var ret = new List<Hook> ();
		var dir = get_hooks_dir ();
		foreach (var name in Click.Dir.open (dir)) {
			if (! name.has_suffix (".hook"))
				continue;
			var path = Path.build_filename (dir, name);
			try {
				var hook = new Hook (db, name[0:-5]);
				hook.fields = parse_deb822_file (path);
				if (hook_name == null ||
				    hook.get_hook_name () == hook_name)
					ret.prepend (hook);
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
	 * Returns: A list of field names defined by this hook.
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
	get_field (string key) throws HooksError
	{
		string value = fields[key.down ()];
		if (value == null)
			throw new HooksError.MISSING_FIELD
				("Hook '%s' has no field named '%s'",
				 name, key);
		return value;
	}

	/**
	 * is_user_level:
	 *
	 * True if this hook is a user-level hook, otherwise false.
	 */
	public bool is_user_level { get {
		return fields["user-level"] == "yes";
	} }

	/**
	 * is_single_version:
	 *
	 * True if this hook is a single-version hook, otherwise false.
	 */
	public bool is_single_version { get {
		return is_user_level || fields["single-version"] == "yes";
	} }

	/**
	 * get_hook_name:
	 *
	 * Returns: This hook's Hook-Name field, or the base of its file
	 * name with the ".hook" extension removed if that field is missing.
	 */
	public string
	get_hook_name () {
		if (fields.has_key ("hook-name"))
			return fields["hook-name"];
		else
			return name;
	}

	/**
	 * get_short_app_id:
	 * @package: A package name.
	 * @app_name: An application name.
	 *
	 * Returns: The short application ID based on @package and
	 * @app_name.
	 */
	public string
	get_short_app_id (string package, string app_name) throws HooksError
	{
		/* TODO: Perhaps this check belongs further up the stack
		 * somewhere?
		 */
		if ("_" in app_name || "/" in app_name)
			throw new HooksError.BAD_APP_NAME
				("Application name '%s' may not contain _ " +
				 "or / characters", app_name);
		return @"$(package)_$(app_name)";
	}

	/**
	 * get_app_id:
	 * @package: A package name.
	 * @version: A version string.
	 * @app_name: An application name.
	 *
	 * Returns: The application ID based on @package, @version, and
	 * @app_name.
	 */
	public string
	get_app_id (string package, string version, string app_name)
		throws HooksError
	{
		var short_app_id = get_short_app_id (package, app_name);
		return @"$(short_app_id)_$(version)";
	}

	private string?
	get_user_home (string? user_name)
	{
		if (user_name == null)
			return null;
		/* TODO: caching */
		unowned Posix.Passwd? pw = Posix.getpwnam (user_name);
		if (pw == null)
			return null;
		return pw.pw_dir;
	}

	/**
	 * get_pattern:
	 * @package: A package name.
	 * @version: A version string.
	 * @app_name: An application name.
	 * @user_name: (allow-none): A user name, or null.
	 */
	public string
	get_pattern (string package, string version, string app_name,
		     string? user_name = null) throws HooksError
	{
		var builder = new VariantBuilder (new VariantType ("a{sms}"));
		var app_id = get_app_id (package, version, app_name);
		var pattern = get_field ("pattern");
		var user_home = get_user_home (user_name);
		builder.add ("{sms}", "id", app_id);
		builder.add ("{sms}", "user", user_name);
		builder.add ("{sms}", "home", user_home);
		if (is_single_version) {
			var short_app_id = get_short_app_id (package,
							     app_name);
			builder.add ("{sms}", "short-id", short_app_id);
		}
		var ret = pattern_format (pattern, builder.end ());
		var len = ret.length;
		while (len > 0) {
			if (ret[len - 1] == Path.DIR_SEPARATOR)
				--len;
			else
				break;
		}
		if (len == ret.length)
			return ret;
		else
			return ret.substring (0, len);
	}

	private void
	priv_drop_failure (string name) throws HooksError
	{
		throw new HooksError.DROP_PRIVS
			("Cannot drop privileges (%s): %s",
			 name, strerror (errno));
	}

	/* This function is not async-signal-safe, but runs between fork() and
	 * execve().  As such, it is not safe to run hooks from a multi-threaded
	 * process.  Do not use the GLib main loop with this!
	 */
	private void
	drop_privileges_inner (string user_name) throws HooksError
	{
		if (Posix.geteuid () != 0)
			return;

		errno = 0;
		unowned Posix.Passwd? pw = Posix.getpwnam (user_name);
		if (pw == null)
			throw new HooksError.NO_SUCH_USER
				("Cannot get password file entry for user " +
				 "'%s': %s", user_name, strerror (errno));
		Posix.gid_t[] supp = {};
		Posix.setgrent ();
		unowned PosixExtra.Group? gr;
		while ((gr = PosixExtra.getgrent ()) != null) {
			foreach (unowned string member in gr.gr_mem) {
				if (member == user_name) {
					supp += gr.gr_gid;
					break;
				}
			}
		}
		Posix.endgrent ();
		if (PosixExtra.setgroups (supp.length, supp) < 0)
			priv_drop_failure ("setgroups");
		/* Portability note: this assumes that we have
		 * [gs]etres[gu]id, which is true on Linux but not
		 * necessarily elsewhere.  If you need to support something
		 * else, there are reasonably standard alternatives
		 * involving other similar calls; see e.g.
		 * gnulib/lib/idpriv-drop.c.
		 */
		if (PosixExtra.setresgid (pw.pw_gid, pw.pw_gid, pw.pw_gid) < 0)
			priv_drop_failure ("setresgid");
		if (PosixExtra.setresuid (pw.pw_uid, pw.pw_uid, pw.pw_uid) < 0)
			priv_drop_failure ("setresuid");
		{
			Posix.uid_t ruid, euid, suid;
			Posix.gid_t rgid, egid, sgid;
			assert (PosixExtra.getresuid (out ruid, out euid,
						      out suid) == 0 &&
				ruid == pw.pw_uid && euid == pw.pw_uid &&
				suid == pw.pw_uid);
			assert (PosixExtra.getresgid (out rgid, out egid,
						      out sgid) == 0 &&
				rgid == pw.pw_gid && egid == pw.pw_gid &&
				sgid == pw.pw_gid);
		}
		Environment.set_variable ("HOME", pw.pw_dir, true);
		Posix.umask (get_umask () | Posix.S_IWOTH);
	}

	private void
	drop_privileges (string user_name)
	{
		try {
			drop_privileges_inner (user_name);
		} catch (HooksError e) {
			error ("%s", e.message);
		}
	}

	/**
	 * get_run_commands_user:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Returns: The user name under which this hook will be run.
	 */
	public string
	get_run_commands_user (string? user_name = null) throws HooksError
	{
		if (is_user_level)
			return user_name;
		return get_field ("user");
	}

	/**
	 * run_commands:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Run any commands specified by the hook to keep itself up to date.
	 */
	public void
	run_commands (string? user_name = null) throws Error
	{
		if (fields.has_key ("exec")) {
			string[] argv = {"/bin/sh", "-c", fields["exec"]};
			var target_user_name = get_run_commands_user
				(user_name);
			SpawnChildSetupFunc drop =
				() => drop_privileges (target_user_name);
			int exit_status;
			Process.spawn_sync (null, argv, null,
					    SpawnFlags.SEARCH_PATH, drop,
					    null, null, out exit_status);
			Process.check_exit_status (exit_status);
		}

		if (fields["trigger"] == "yes")
			throw new HooksError.NYI
				("'Trigger: yes' not yet implemented");
	}

	private List<PreviousEntry>
	get_previous_entries (string? user_name = null) throws Error
	{
		var ret = new List<PreviousEntry> ();
		var link_dir_path = Path.get_dirname (get_pattern
			("", "", "", user_name));
		/* TODO: This only works if the application ID only appears, at
		 * most, in the last component of the pattern path.
		 */
		foreach (var entry in Click.Dir.open (link_dir_path)) {
			var path = Path.build_filename (link_dir_path, entry);
			var exp_builder = new VariantBuilder
				(new VariantType ("a{sms}"));
			exp_builder.add ("{sms}", "user", user_name);
			exp_builder.add
				("{sms}", "home", get_user_home (user_name));
			var exp = pattern_possible_expansion
				(path, fields["pattern"], exp_builder.end ());
			unowned string? id = null;
			if (exp != null)
				exp.lookup ("id", "&s", out id);
			if (id == null)
				continue;
			var tokens = id.split ("_", 3);
			if (tokens.length < 3)
				continue;
			/* tokens == { package, app_name, version } */
			ret.prepend (new PreviousEntry
				(path, tokens[0], tokens[2], tokens[1]));
		}
		ret.reverse ();
		return ret;
	}

	/**
	 * install_link:
	 * @package: A package name.
	 * @version: A version string.
	 * @app_name: An application name.
	 * @relative_path: A relative path within the unpacked package.
	 * @user_name: (allow-none): A user name, or null.
	 * @user_db: (allow-none): A #Click.User, or null.
	 *
	 * Install a hook symlink.
	 *
	 * This should be called with dropped privileges if necessary.
	 */
	private void
	install_link (string package, string version, string app_name,
		      string relative_path, string? user_name = null,
		      User? user_db = null) throws Error
	{
		string path;
		if (is_user_level)
			path = user_db.get_path (package);
		else
			path = db.get_path (package, version);
		var target = Path.build_filename (path, relative_path);
		var link = get_pattern (package, version, app_name, user_name);
		if (is_symlink (link) && FileUtils.read_link (link) == target)
			return;
		ensuredir (Path.get_dirname (link));
		symlink_force (target, link);
	}

	/**
	 * install_package:
	 * @package: A package name.
	 * @version: A version string.
	 * @app_name: An application name.
	 * @relative_path: A relative path within the unpacked package.
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Run this hook in response to @package being installed.
	 */
	public void
	install_package (string package, string version, string app_name,
			 string relative_path, string? user_name = null)
		throws Error
	{
		if (! is_user_level)
			assert (user_name == null);

		/* Remove previous versions if necessary. */
		if (is_single_version) {
			var entries = get_previous_entries (user_name);
			foreach (var prev in entries) {
				if (prev.package == package &&
				    prev.app_name == app_name &&
				    prev.version != version)
					unlink_force (prev.path);
			}
		}

		if (is_user_level) {
			var user_db = new User.for_user (db, user_name);
			user_db.drop_privileges ();
			try {
				install_link (package, version, app_name,
					      relative_path, user_name,
					      user_db);
			} finally {
				user_db.regain_privileges ();
			}
		} else
			install_link (package, version, app_name,
				      relative_path);
		run_commands (user_name);
	}

	/**
	 * remove_package:
	 * @package: A package name.
	 * @version: A version string.
	 * @app_name: An application name.
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Run this hook in response to @package being removed.
	 */
	public void
	remove_package (string package, string version, string app_name,
			string? user_name = null) throws Error
	{
		unlink_force (get_pattern
			(package, version, app_name, user_name));
		run_commands (user_name);
	}

	private Gee.ArrayList<UnpackedPackage>
	get_all_packages_for_user (string user_name, User user_db) throws Error
	{
		var ret = new Gee.ArrayList<UnpackedPackage> ();
		foreach (var package in user_db.get_package_names ())
			ret.add (new UnpackedPackage
				(package, user_db.get_version (package),
				 user_name));
		return ret;
	}

	/**
	 * get_all_packages:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Return a list of all unpacked packages.
	 *
	 * If running a user-level hook, this returns (package, version,
	 * user) for the current version of each package registered for each
	 * user, or only for a single user if user is not null.
	 *
	 * If running a system-level hook, this returns (package, version,
	 * null) for each version of each unpacked package.
	 *
	 * Returns: A list of all unpacked packages.
	 */
	private List<UnpackedPackage>
	get_all_packages (string? user_name = null) throws Error
	{
		var ret = new Gee.ArrayList<UnpackedPackage> ();
		if (is_user_level) {
			if (user_name != null) {
				var user_db = new User.for_user
					(db, user_name);
				ret.add_all (get_all_packages_for_user
					(user_name, user_db));
			} else {
				var users_db = new Users (db);
				var user_names = users_db.get_user_names ();
				foreach (var one_user_name in user_names) {
					if (one_user_name.has_prefix ("@"))
						continue;
					var one_user_db = users_db.get_user
						(one_user_name);
					ret.add_all (get_all_packages_for_user
						(one_user_name, one_user_db));
				}
			}
		} else {
			foreach (var inst in db.get_packages ())
				ret.add (new UnpackedPackage
					(inst.package, inst.version));
		}
		/* Flatten into a List to avoid introspection problems in
		 * case this method is ever exposed.
		 */
		var ret_list = new List<UnpackedPackage> ();
		foreach (var element in ret)
			ret_list.prepend (element);
		ret_list.reverse ();
		return ret_list;
	}

	/**
	 * get_relevant_apps:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Returns: A list of all applications relevant for this hook.
	 */
	private List<RelevantApp>
	get_relevant_apps (string? user_name = null) throws Error
	{
		var ret = new List<RelevantApp> ();
		var hook_name = get_hook_name ();
		foreach (var unpacked in get_all_packages (user_name)) {
			var manifest = read_manifest_hooks
				(db, unpacked.package, unpacked.version);
			foreach (var app_name in manifest.get_members ()) {
				var hooks = manifest.get_object_member
					(app_name);
				if (hooks.has_member (hook_name)) {
					var relative_path = hooks.get_string_member
						(hook_name);
					ret.prepend (new RelevantApp
						(unpacked.package,
						 unpacked.version, app_name,
						 unpacked.user_name,
						 relative_path));
				}
			}
		}
		ret.reverse ();
		return ret;
	}

	/**
	 * install:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Install files associated with this hook for any packages that
	 * attach to it.
	 */
	public void
	install (string? user_name = null) throws Error
	{
		foreach (var app in get_relevant_apps (user_name))
			install_package (app.package, app.version,
					 app.app_name, app.relative_path,
					 app.user_name);
	}

	/**
	 * remove:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Remove files associated with this hook for any packages that
	 * attach to it.
	 */
	public void
	remove (string? user_name = null) throws Error
	{
		foreach (var app in get_relevant_apps (user_name))
			remove_package (app.package, app.version, app.app_name,
					app.user_name);
	}

	/**
	 * sync:
	 * @user_name: (allow-none): A user name, or null.
	 *
	 * Run a hook for all installed packages (system-level if @user_name
	 * is null, otherwise user-level).
	 *
	 * This is useful to catch up with preinstalled packages.
	 */
	public void
	sync (string? user_name = null) throws Error
	{
		if (! is_user_level)
			assert (user_name == null);

		var seen = new Gee.HashSet<string> ();
		foreach (var app in get_relevant_apps (user_name)) {
			unowned string package = app.package;
			unowned string version = app.version;
			unowned string app_name = app.app_name;
			seen.add (@"$(package)_$(app_name)_$(version)");
			if (is_user_level) {
				var user_db = new User.for_user
					(db, user_name);
				user_db.drop_privileges ();
				try {
					user_db.raw_set_version
						(package, version);
					install_link (package, version,
						      app_name,
						      app.relative_path,
						      app.user_name, user_db);
				} finally {
					user_db.regain_privileges ();
				}
			} else
				install_link (package, version, app_name,
					      app.relative_path);
		}

		foreach (var prev in get_previous_entries (user_name)) {
			unowned string package = prev.package;
			unowned string version = prev.version;
			unowned string app_name = prev.app_name;
			if (! (@"$(package)_$(app_name)_$(version)" in seen))
				unlink_force (prev.path);
		}

		run_commands (user_name);
	}
}

private Gee.TreeSet<AppHook>
get_app_hooks (Json.Object manifest)
{
	var items = new Gee.TreeSet<AppHook> ();  /* sorted */
	foreach (var app_name in manifest.get_members ()) {
		var hooks = manifest.get_object_member (app_name);
		foreach (var hook_name in hooks.get_members ())
			items.add (new AppHook (app_name, hook_name));
	}
	return items;
}

/**
 * package_install_hooks:
 * @db: A #Click.DB.
 * @package: A package name.
 * @old_version: (allow-none): The old version of the package, or null.
 * @new_version: The new version of the package.
 * @user_name: (allow-none): A user name, or null.
 *
 * Run hooks following removal of a Click package.
 *
 * If @user_name is null, only run system-level hooks.  If @user_name is not
 * null, only run user-level hooks for that user.
 */
public void
package_install_hooks (DB db, string package, string? old_version,
		       string new_version, string? user_name = null)
	throws Error
{
	var old_manifest = read_manifest_hooks (db, package, old_version);
	var new_manifest = read_manifest_hooks (db, package, new_version);

	/* Remove any targets for single-version hooks that were in the old
	 * manifest but not the new one.
	 */
	var old_app_hooks = get_app_hooks (old_manifest);
	var new_app_hooks = get_app_hooks (new_manifest);
	foreach (var app_hook in new_app_hooks)
		old_app_hooks.remove (app_hook);
	foreach (var app_hook in old_app_hooks) {
		foreach (var hook in Hook.open_all (db, app_hook.hook_name)) {
			if (hook.is_user_level != (user_name != null))
				continue;
			if (! hook.is_single_version)
				continue;
			hook.remove_package (package, old_version,
					     app_hook.app_name, user_name);
		}
	}

	var new_app_names = new_manifest.get_members ();
	new_app_names.sort (strcmp);
	foreach (var app_name in new_app_names) {
		var app_hooks = new_manifest.get_object_member (app_name);
		var hook_names = app_hooks.get_members ();
		hook_names.sort (strcmp);
		foreach (var hook_name in hook_names) {
			var relative_path = app_hooks.get_string_member
				(hook_name);
			foreach (var hook in Hook.open_all (db, hook_name)) {
				if (hook.is_user_level != (user_name != null))
					continue;
				hook.install_package (package, new_version,
						      app_name, relative_path,
						      user_name);
			}
		}
	}
}

/**
 * package_remove_hooks:
 * @db: A #Click.DB.
 * @package: A package name.
 * @old_version: The old version of the package.
 * @user_name: (allow-none): A user name, or null.
 *
 * Run hooks following removal of a Click package.
 *
 * If @user_name is null, only run system-level hooks.  If @user_name is not
 * null, only run user-level hooks for that user.
 */
public void
package_remove_hooks (DB db, string package, string old_version,
		      string? user_name = null) throws Error
{
	var old_manifest = read_manifest_hooks (db, package, old_version);

	foreach (var app_hook in get_app_hooks (old_manifest)) {
		foreach (var hook in Hook.open_all (db, app_hook.hook_name)) {
			if (hook.is_user_level != (user_name != null))
				continue;
			hook.remove_package (package, old_version,
					     app_hook.app_name, user_name);
		}
	}
}

/**
 * run_system_hooks:
 * @db: A #Click.DB.
 *
 * Run system-level hooks for all installed packages.
 *
 * This is useful when starting up from images with preinstalled packages
 * which may not have had their system-level hooks run properly when
 * building the image.  It is suitable for running at system startup.
 */
public void
run_system_hooks (DB db) throws Error
{
	db.ensure_ownership ();
	foreach (var hook in Hook.open_all (db)) {
		if (! hook.is_user_level)
			hook.sync ();
	}
}

/**
 * run_user_hooks:
 * @db: A #Click.DB.
 * @user_name: (allow-none): A user name, or null to run hooks for the
 * current user.
 *
 * Run user-level hooks for all installed packages.
 *
 * This is useful to catch up with packages that may have been preinstalled
 * and registered for all users.  It is suitable for running at session
 * startup.
 */
public void
run_user_hooks (DB db, string? user_name = null) throws Error
{
	if (user_name == null)
		user_name = Environment.get_user_name ();
	foreach (var hook in Hook.open_all (db)) {
		if (hook.is_user_level)
			hook.sync (user_name);
	}
}

}
