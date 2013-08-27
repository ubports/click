/* -*- Mode: C; tab-width: 8; indent-tabs-mode: t; c-basic-offset: 8 -*-
 *
 * Copyright (C) 2010-2013 Matthias Klumpp <matthias@tenstral.net>
 * Copyright (C) 2011 Richard Hughes <richard@hughsie.com>
 * Copyright (C) 2013 Canonical Ltd.
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

#include <errno.h>
#include <pwd.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

#include <gio/gio.h>
#include <glib.h>
#include <glib-object.h>
#include <json-glib/json-glib.h>
#define I_KNOW_THE_PACKAGEKIT_GLIB2_API_IS_SUBJECT_TO_CHANGE
#include <packagekit-glib2/packagekit.h>
#define I_KNOW_THE_PACKAGEKIT_PLUGIN_API_IS_SUBJECT_TO_CHANGE
#include <plugin/packagekit-plugin.h>

#if PK_CHECK_VERSION(0,8,1) && !PK_CHECK_VERSION(0,8,10)
#error "PackageKit >= 0.8.1 and < 0.8.10 not supported"
#endif


struct PkPluginPrivate {
	guint			 dummy;
};

#define DEFAULT_PATH \
	"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

/**
 * click_is_click_package:
 *
 * Check if a given file is a Click package.
 */
static gboolean
click_is_click_package (const gchar *filename)
{
	gboolean ret = FALSE;
	GFile *file;
	GFileInfo *info = NULL;
	const gchar *content_type;

	file = g_file_new_for_path (filename);
	info = g_file_query_info (file, G_FILE_ATTRIBUTE_STANDARD_CONTENT_TYPE,
				  G_FILE_QUERY_INFO_NONE, NULL, NULL);
	if (!info)
		goto out;
	content_type = g_file_info_get_content_type (info);
	if (strcmp (content_type, "application/x-click") == 0)
		ret = TRUE;

out:
	if (info)
		g_object_unref (info);
	g_object_unref (file);
	return ret;
}

static gchar **
click_filter_click_packages (PkTransaction *transaction, gchar **files)
{
	gchar **native_files = NULL;
	gchar **click_files = NULL;
	GPtrArray *native = NULL;
	GPtrArray *click = NULL;
	gint i;
	gboolean ret = FALSE;

	/* Are there any Click packages at all?  If not, we can bail out
	 * early.
	 */
	for (i = 0; files[i]; ++i) {
		ret = click_is_click_package (files[i]);
		if (ret)
			break;
	}
	if (!ret)
		goto out;

	/* Find and filter Click packages. */
	native = g_ptr_array_new_with_free_func (g_free);
	click = g_ptr_array_new_with_free_func (g_free);

	for (i = 0; files[i]; ++i) {
		ret = click_is_click_package (files[i]);
		g_ptr_array_add (ret ? click : native, g_strdup (files[i]));
	}

	native_files = pk_ptr_array_to_strv (native);
	click_files = pk_ptr_array_to_strv (click);
	pk_transaction_set_full_paths (transaction, native_files);

out:
	g_strfreev (native_files);
	if (native)
		g_ptr_array_unref (native);
	if (click)
		g_ptr_array_unref (click);
	return click_files;
}

/**
 * click_get_username_for_uid:
 *
 * Return the username corresponding to a given user ID, or NULL.  The
 * caller is responsible for freeing the result.
 */
static gchar *
click_get_username_for_uid (uid_t uid)
{
	struct passwd pwbuf, *pwbufp;
	char *buf = NULL;
	size_t buflen;
	gchar *username = NULL;

	buflen = sysconf (_SC_GETPW_R_SIZE_MAX);
	if (buflen == -1)
		buflen = 1024;
	buf = g_malloc (buflen);
	for (;;) {
		int ret;

		/* TODO: getpwuid_r is apparently a portability headache;
		 * see glib/gio/glocalfileinfo.c.  But for now we only care
		 * about Linux.
		 */
		ret = getpwuid_r (uid, &pwbuf, buf, buflen, &pwbufp);
		if (pwbufp)
			break;
		if (ret != ERANGE)
			goto out;

		buflen *= 2;  /* TODO: check overflow */
		buf = g_realloc (buf, buflen);
	}

	username = g_strdup (pwbuf.pw_name);

out:
	g_free (buf);
	return username;
}

/**
 * click_get_envp:
 *
 * Return the environment needed by click.  This is the same as the
 * environment we got, except with a reasonable PATH (PackageKit clears its
 * environment by default).
 */
static gchar **
click_get_envp (void)
{
	gchar **environ;
	gchar **env_item;
	guint env_len;

	environ = g_get_environ ();
	env_len = 0;
	for (env_item = environ; env_item && *env_item; ++env_item) {
		if (strncmp (*env_item, "PATH=", sizeof ("PATH=") - 1) == 0)
			return environ;
		++env_len;
	}

	env_len = environ ? g_strv_length (environ) : 0;
	environ = g_realloc_n (environ, env_len + 2, sizeof (*environ));
	environ[env_len] = g_strdup ("PATH=" DEFAULT_PATH);
	environ[env_len + 1] = NULL;
	return environ;
}

static JsonParser *
click_get_manifest (const gchar *filename)
{
	gboolean ret;
	gchar **argv = NULL;
	gint i;
	gchar **envp = NULL;
	gchar *manifest_text = NULL;
	JsonParser *parser = NULL;

	/* TODO: debug messages on failure */

	argv = g_malloc0_n (4, sizeof (*argv));
	i = 0;
	argv[i++] = g_strdup ("click");
	argv[i++] = g_strdup ("info");
	argv[i++] = g_strdup (filename);
	envp = click_get_envp ();
	ret = g_spawn_sync (NULL, argv, envp,
			    G_SPAWN_SEARCH_PATH | G_SPAWN_STDERR_TO_DEV_NULL,
			    NULL, NULL, &manifest_text, NULL, NULL, NULL);
	if (!ret)
		goto out;

	parser = json_parser_new ();
	if (!parser)
		goto out;
	json_parser_load_from_data (parser, manifest_text, -1, NULL);

out:
	g_strfreev (argv);
	g_strfreev (envp);
	g_free (manifest_text);

	return parser;
}

static gchar *
click_get_field (JsonParser *parser, const gchar *field)
{
	JsonNode *node = NULL;

	node = json_parser_get_root (parser);
	node = json_object_get_member (json_node_get_object (node), field);
	if (!node)
		return NULL;
	return json_node_dup_string (node);
}

static JsonParser *
click_get_list (PkTransaction *transaction)
{
	gboolean ret;
	gchar **argv = NULL;
	gint i;
	gchar *username = NULL;
	gchar **envp = NULL;
	gchar *list_text = NULL;
	JsonParser *parser = NULL;

	/* TODO: debug messages on failure */

	argv = g_malloc0_n (5, sizeof (*argv));
	i = 0;
	argv[i++] = g_strdup ("click");
	argv[i++] = g_strdup ("list");
	argv[i++] = g_strdup ("--manifest");
	username = click_get_username_for_uid
		(pk_transaction_get_uid (transaction));
	if (username)
		argv[i++] = g_strdup_printf ("--user=%s", username);
	envp = click_get_envp ();
	ret = g_spawn_sync (NULL, argv, envp,
			    G_SPAWN_SEARCH_PATH | G_SPAWN_STDERR_TO_DEV_NULL,
			    NULL, NULL, &list_text, NULL, NULL, NULL);
	if (!ret)
		goto out;

	parser = json_parser_new ();
	if (!parser)
		goto out;
	json_parser_load_from_data (parser, list_text, -1, NULL);

out:
	g_strfreev (argv);
	g_free (username);
	g_strfreev (envp);
	g_free (list_text);

	return parser;
}

static gchar *
click_build_pkid (const gchar *filename, const gchar *data)
{
	JsonParser *parser = NULL;
	gchar *name = NULL;
	gchar *version = NULL;
	gchar *architecture = NULL;
	gchar *pkid = NULL;

	parser = click_get_manifest (filename);
	if (!parser)
		goto out;
	name = click_get_field (parser, "name");
	version = click_get_field (parser, "version");
	architecture = click_get_field (parser, "architecture");
	pkid = pk_package_id_build (name, version, architecture, data);

out:
	g_clear_object (&parser);
	g_free (name);
	g_free (version);
	g_free (architecture);
	return pkid;
}

static gboolean
click_install_file (PkPlugin *plugin, PkTransaction *transaction,
		    const gchar *filename)
{
	gboolean ret = FALSE;
	gchar **argv = NULL;
	gint i;
	gchar *username = NULL;
	gchar **envp = NULL;
	gchar *pkid = NULL;

	argv = g_malloc0_n (6, sizeof (*argv));
	i = 0;
	argv[i++] = g_strdup ("click");
	argv[i++] = g_strdup ("install");
	username = click_get_username_for_uid
		(pk_transaction_get_uid (transaction));
	if (username)
		argv[i++] = g_strdup_printf ("--user=%s", username);
	/* TODO: make configurable */
	argv[i++] = g_strdup ("--force-missing-framework");
	argv[i++] = g_strdup (filename);
	envp = click_get_envp ();
	ret = g_spawn_sync (NULL, argv, envp,
			    G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL |
			    G_SPAWN_STDERR_TO_DEV_NULL,
			    NULL, NULL, NULL, NULL, NULL, NULL);
	if (!ret)
		goto out;

	pkid = click_build_pkid (filename, "installed");
#if PK_CHECK_VERSION(0,8,10)
	if (!pk_backend_job_get_is_error_set (plugin->job)) {
		pk_backend_job_package (plugin->job, PK_INFO_ENUM_INSTALLED,
					pkid, "summary goes here");
		ret = TRUE;
	}
#else
	if (!pk_backend_get_is_error_set (plugin->backend)) {
		pk_backend_package (plugin->backend, PK_INFO_ENUM_INSTALLED,
				    pkid, "summary goes here");
		ret = TRUE;
	}
#endif

out:
	g_strfreev (argv);
	g_free (username);
	g_strfreev (envp);
	g_free (pkid);

	return ret;
}

static void
click_install_files (PkPlugin *plugin, PkTransaction *transaction,
		     gchar **filenames)
{
	gboolean ret = FALSE;
	gint i;

	for (i = 0; filenames[i]; ++i) {
		g_debug ("Click: installing %s", filenames[i]);
		ret = click_install_file (plugin, transaction, filenames[i]);
		if (!ret)
			break;
	}
}

static void
click_get_packages_one (JsonArray *array, guint index, JsonNode *element_node,
			gpointer data)
{
	PkPlugin *plugin;
	JsonObject *manifest;
	const gchar *name;
	const gchar *version;
	const gchar *architecture = NULL;
	const gchar *title = NULL;
	gchar *pkid = NULL;

	plugin = (PkPlugin *) data;
	manifest = json_node_get_object (element_node);
	if (!manifest)
		return;
	name = json_object_get_string_member (manifest, "name");
	if (!name)
		return;
	version = json_object_get_string_member (manifest, "version");
	if (!version)
		return;
	if (json_object_has_member (manifest, "architecture"))
		architecture = json_object_get_string_member (manifest,
							      "architecture");
	if (!architecture)
		architecture = "";
	if (json_object_has_member (manifest, "title"))
		title = json_object_get_string_member (manifest, "title");
	if (!title)
		title = "";

	pkid = pk_package_id_build (name, version, architecture,
				    "installed:click");
#if PK_CHECK_VERSION(0,8,10)
	pk_backend_job_package (plugin->job, PK_INFO_ENUM_INSTALLED, pkid,
				title);
#else
	pk_backend_package (plugin->backend, PK_INFO_ENUM_INSTALLED, pkid,
			    title);
#endif
}

static void
click_get_packages (PkPlugin *plugin, PkTransaction *transaction)
{
	JsonParser *parser = NULL;
	JsonNode *node = NULL;
	JsonArray *array = NULL;

	parser = click_get_list (transaction);
	if (!parser)
		goto out;
	node = json_parser_get_root (parser);
	array = json_node_get_array (node);
	if (!array)
		goto out;
	json_array_foreach_element (array, click_get_packages_one, plugin);

out:
	g_clear_object (&parser);
}

static void
click_skip_native_backend (PkPlugin *plugin)
{
#if PK_CHECK_VERSION(0,8,10)
	if (!pk_backend_job_get_is_error_set (plugin->job))
		pk_backend_job_set_exit_code (plugin->job,
					      PK_EXIT_ENUM_SKIP_TRANSACTION);
#else
	if (!pk_backend_get_is_error_set (plugin->backend)) {
		pk_backend_set_exit_code (plugin->backend,
					  PK_EXIT_ENUM_SKIP_TRANSACTION);
		/* Work around breakage in PackageKit 0.7; if we omit this
		 * then transaction signals are not all disconnected and
		 * later transactions may crash.
		 */
		pk_backend_finished (plugin->backend);
	}
#endif
}

/**
 * pk_plugin_get_description:
 */
const gchar *
pk_plugin_get_description (void)
{
	return "Support for Click packages";
}

/**
 * pk_plugin_initialize:
 */
void
pk_plugin_initialize (PkPlugin *plugin)
{
	/* create private area */
	plugin->priv = PK_TRANSACTION_PLUGIN_GET_PRIVATE (PkPluginPrivate);

	/* tell PK we might be able to handle these */
#if !PK_CHECK_VERSION(0,8,10)
	pk_backend_implement (plugin->backend,
			      PK_ROLE_ENUM_SIMULATE_INSTALL_FILES);
#endif
	pk_backend_implement (plugin->backend, PK_ROLE_ENUM_INSTALL_FILES);
	pk_backend_implement (plugin->backend, PK_ROLE_ENUM_GET_PACKAGES);
}

/**
 * pk_plugin_transaction_content_types:
 */
void
pk_plugin_transaction_content_types (PkPlugin *plugin,
				     PkTransaction *transaction)
{
	pk_transaction_add_supported_content_type (transaction,
						   "application/x-click");
}

/**
 * pk_plugin_transaction_started:
 */
void
pk_plugin_transaction_started (PkPlugin *plugin, PkTransaction *transaction)
{
	PkRoleEnum role;
	gchar **full_paths = NULL;
	gchar **click_files = NULL;
#if PK_CHECK_VERSION(0,8,10)
	PkBitfield flags;
#endif
	gboolean simulating;

	g_debug ("Processing transaction");

#if PK_CHECK_VERSION(0,8,10)
	/* reset the native backend job */
	pk_backend_job_reset (plugin->job);
	pk_backend_job_set_status (plugin->job, PK_STATUS_ENUM_SETUP);
#else
	/* reset the native backend */
	pk_backend_reset (plugin->backend);
	pk_backend_set_status (plugin->backend, PK_STATUS_ENUM_SETUP);
#endif

	role = pk_transaction_get_role (transaction);

#if PK_CHECK_VERSION(0,8,10)
	flags = pk_transaction_get_transaction_flags (transaction);
	simulating = pk_bitfield_contain (flags,
					  PK_TRANSACTION_FLAG_ENUM_SIMULATE);
#else
	switch (role) {
		case PK_ROLE_ENUM_SIMULATE_INSTALL_FILES:
		case PK_ROLE_ENUM_SIMULATE_INSTALL_PACKAGES:
		case PK_ROLE_ENUM_SIMULATE_REMOVE_PACKAGES:
		case PK_ROLE_ENUM_SIMULATE_UPDATE_PACKAGES:
		case PK_ROLE_ENUM_SIMULATE_REPAIR_SYSTEM:
			simulating = TRUE;
			break;

		default:
			simulating = FALSE;
			break;
	}
#endif

	switch (role) {
#if !PK_CHECK_VERSION(0,8,10)
		case PK_ROLE_ENUM_SIMULATE_INSTALL_FILES:
#endif
		case PK_ROLE_ENUM_INSTALL_FILES:
			/* TODO: Simulation needs to be smarter - backend
			 * needs to Simulate() with remaining packages.
			 */
			full_paths = pk_transaction_get_full_paths
				(transaction);
			click_files = click_filter_click_packages (transaction,
								   full_paths);
			if (!simulating && click_files)
				click_install_files (plugin, transaction,
						     click_files);

			full_paths = pk_transaction_get_full_paths
				(transaction);
			if (g_strv_length (full_paths) == 0)
				click_skip_native_backend (plugin);
			break;

		case PK_ROLE_ENUM_GET_PACKAGES:
			/* TODO: Handle simulation? */
			if (!simulating)
				click_get_packages (plugin, transaction);
			break;

		default:
			break;
	}

	g_strfreev (click_files);
}

/**
 * pk_plugin_transaction_get_action:
 **/
const gchar *
pk_plugin_transaction_get_action (PkPlugin *plugin, PkTransaction *transaction,
				  const gchar *action_id)
{
	const gchar *install_actions[] = {
		"org.freedesktop.packagekit.package-install",
		"org.freedesktop.packagekit.package-install-untrusted",
		NULL
	};
	const gchar **install_action;
	gchar **full_paths;
	gint i;

	if (!action_id)
		return NULL;

	for (install_action = install_actions; *install_action;
	     ++install_action) {
		if (strcmp (action_id, *install_action) == 0) {
			/* Use an action with weaker auth requirements if
			 * and only if all the packages in the list are
			 * Click packages.
			 */
			full_paths = pk_transaction_get_full_paths
				(transaction);
			for (i = 0; full_paths[i]; ++i) {
				if (!click_is_click_package (full_paths[i]))
					break;
			}
			if (!full_paths[i])
				return "com.ubuntu.click.package-install";
		}
	}

	return action_id;
}
