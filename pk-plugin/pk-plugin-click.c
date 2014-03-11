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

#define _GNU_SOURCE

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

#include "click.h"


struct PkPluginPrivate {
	guint			 dummy;
};

#define DEFAULT_PATH \
	"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

/**
 * click_is_click_file:
 *
 * Check if a given file is a Click package file.
 */
static gboolean
click_is_click_file (const gchar *filename)
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
click_filter_click_files (PkTransaction *transaction, gchar **files)
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
		ret = click_is_click_file (files[i]);
		if (ret)
			break;
	}
	if (!ret)
		goto out;

	/* Find and filter Click packages. */
	native = g_ptr_array_new_with_free_func (g_free);
	click = g_ptr_array_new_with_free_func (g_free);

	for (i = 0; files[i]; ++i) {
		ret = click_is_click_file (files[i]);
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

static gboolean
click_pkid_data_is_click (const gchar *data)
{
	gchar **tokens;
	gboolean ret;

	tokens = g_strsplit (data, ",", 2);
	ret = g_strcmp0 (tokens[0], "local:click") == 0 ||
	      g_strcmp0 (tokens[0], "installed:click") == 0;
	g_strfreev (tokens);

	return ret;
}

/**
 * click_is_click_package:
 *
 * Check if a given PackageKit package-id is a Click package.
 */
static gboolean
click_is_click_package (const gchar *package_id)
{
	gchar **parts = NULL;
	gboolean ret = FALSE;

	parts = pk_package_id_split (package_id);
	if (!parts)
		goto out;
	ret = click_pkid_data_is_click (parts[PK_PACKAGE_ID_DATA]);

out:
	g_strfreev (parts);
	return ret;
}

static gchar **
click_filter_click_packages (PkTransaction *transaction, gchar **package_ids)
{
	gchar **native_package_ids = NULL;
	gchar **click_package_ids = NULL;
	GPtrArray *native = NULL;
	GPtrArray *click = NULL;
	gint i;
	gboolean ret = FALSE;

	/* Are there any Click packages at all?  If not, we can bail out
	 * early.
	 */
	for (i = 0; package_ids[i]; ++i) {
		ret = click_is_click_package (package_ids[i]);
		if (ret)
			break;
	}
	if (!ret)
		goto out;

	/* Find and filter Click packages. */
	native = g_ptr_array_new_with_free_func (g_free);
	click = g_ptr_array_new_with_free_func (g_free);

	for (i = 0; package_ids[i]; ++i) {
		ret = click_is_click_package (package_ids[i]);
		g_ptr_array_add (ret ? click : native,
				 g_strdup (package_ids[i]));
	}

	native_package_ids = pk_ptr_array_to_strv (native);
	click_package_ids = pk_ptr_array_to_strv (click);
	pk_transaction_set_package_ids (transaction, native_package_ids);

out:
	g_strfreev (native_package_ids);
	if (native)
		g_ptr_array_unref (native);
	if (click)
		g_ptr_array_unref (click);
	return click_package_ids;
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

static void
click_pk_error (PkPlugin *plugin, PkErrorEnum code,
		const char *summary, const char *extra)
{
	if (pk_backend_job_get_is_error_set (plugin->job)) {
		/* PK already has an error; just log this. */
		g_warning ("%s", summary);
		if (extra)
			g_warning ("%s", extra);
	} else if (extra)
		pk_backend_job_error_code
			(plugin->job, code, "%s\n%s", summary, extra);
	else
		pk_backend_job_error_code (plugin->job, code, "%s", summary);
}

static JsonParser *
click_get_manifest (PkPlugin *plugin, const gchar *filename)
{
	gboolean ret;
	gchar **argv = NULL;
	gint i;
	gchar **envp = NULL;
	gchar *manifest_text = NULL;
	gchar *click_stderr = NULL;
	gint click_status;
	JsonParser *parser = NULL;

	argv = g_malloc0_n (4, sizeof (*argv));
	i = 0;
	argv[i++] = g_strdup ("click");
	argv[i++] = g_strdup ("info");
	argv[i++] = g_strdup (filename);
	envp = click_get_envp ();
	ret = g_spawn_sync (NULL, argv, envp, G_SPAWN_SEARCH_PATH,
			    NULL, NULL, &manifest_text, &click_stderr,
			    &click_status, NULL);
	if (!ret)
		goto out;
	if (!g_spawn_check_exit_status (click_status, NULL)) {
		gchar *summary = g_strdup_printf
			("\"click info %s\" failed.", filename);
		click_pk_error (plugin, PK_ERROR_ENUM_INTERNAL_ERROR,
				summary, click_stderr);
		g_free (summary);
		goto out;
	}

	parser = json_parser_new ();
	if (!parser)
		goto out;
	json_parser_load_from_data (parser, manifest_text, -1, NULL);

out:
	g_strfreev (argv);
	g_strfreev (envp);
	g_free (manifest_text);
	g_free (click_stderr);

	return parser;
}

static gchar *
click_get_field_string (JsonObject *manifest, const gchar *field)
{
	JsonNode *node;

	node = json_object_get_member (manifest, field);
	if (!node)
		return NULL;
	return json_node_dup_string (node);
}

static JsonObject *
click_get_field_object (JsonObject *manifest, const gchar *field)
{
	JsonNode *node;

	node = json_object_get_member (manifest, field);
	if (!node)
		return NULL;
	/* Note that this does not take a reference. */
	return json_node_get_object (node);
}

static gboolean
click_get_field_boolean (JsonObject *manifest, const gchar *field,
			 gboolean def)
{
	JsonNode *node;

	node = json_object_get_member (manifest, field);
	if (!node)
		return def;
	return json_node_get_boolean (node);
}

static JsonArray *
click_get_list (PkPlugin *plugin, PkTransaction *transaction)
{
	gchar *username = NULL;
	ClickUser *registry = NULL;
	JsonArray *array = NULL;
	GError *error = NULL;

	username = click_get_username_for_uid
		(pk_transaction_get_uid (transaction));
	registry = click_user_new_for_user (NULL, username, &error);
	if (error) {
		click_pk_error (plugin, PK_ERROR_ENUM_INTERNAL_ERROR,
				"Unable to read Click database.",
				error->message);
		goto out;
	}
	array = click_user_get_manifests (registry, &error);
	if (error) {
		click_pk_error (plugin, PK_ERROR_ENUM_INTERNAL_ERROR,
				"Unable to get Click package manifests.",
				error->message);
		goto out;
	}

out:
	if (error)
		g_error_free (error);
	g_object_unref (registry);
	g_free (username);

	return array;
}

static gchar *
click_build_pkid_data (const gchar *data_prefix, JsonObject *manifest)
{
	gint n_elements = 0;
	gchar **elements = NULL;
	gint i;
	JsonObject *hooks;
	GList *hooks_members = NULL, *hooks_iter;
	gchar *data = NULL;

	hooks = click_get_field_object (manifest, "hooks");

	n_elements = 3;  /* data_prefix, removable, terminator */
	if (hooks)
		n_elements += json_object_get_size (hooks);
	elements = g_new0 (gchar *, n_elements);
	if (!elements)
		goto out;

	i = 0;
	elements[i++] = g_strdup (data_prefix);
	/* A missing "_removable" entry in the manifest means that we just
	 * installed the package, so it must be removable.
	 */
	if (click_get_field_boolean (manifest, "_removable", TRUE))
		elements[i++] = g_strdup ("removable=1");
	else
		elements[i++] = g_strdup ("removable=0");
	if (hooks) {
		hooks_members = json_object_get_members (hooks);
		for (hooks_iter = hooks_members; hooks_iter;
		     hooks_iter = hooks_iter->next) {
			g_assert (i < n_elements - 1);
			elements[i++] = g_strdup_printf
				("app_name=%s", (gchar *) hooks_iter->data);
		}
	}
	elements[i] = NULL;
	data = g_strjoinv (",", elements);

out:
	g_strfreev (elements);
	if (hooks_members)
		g_list_free (hooks_members);
	return data;
}

static gchar *
click_build_pkid (PkPlugin *plugin, JsonObject *manifest,
		  const gchar *data_prefix)
{
	gchar *name = NULL;
	gchar *version = NULL;
	gchar *architecture = NULL;
	gchar *data = NULL;
	gchar *pkid = NULL;

	if (!manifest)
		goto out;
	name = click_get_field_string (manifest, "name");
	if (!name)
		goto out;
	version = click_get_field_string (manifest, "version");
	if (!version)
		goto out;
	architecture = click_get_field_string (manifest, "architecture");
	if (!architecture)
		architecture = g_strdup ("");
	data = click_build_pkid_data (data_prefix, manifest);
	pkid = pk_package_id_build (name, version, architecture, data);

out:
	g_free (name);
	g_free (version);
	g_free (architecture);
	g_free (data);
	return pkid;
}

static gboolean
click_split_pkid (const gchar *package_id, gchar **name, gchar **version,
		  gchar **architecture)
{
	gchar **parts = NULL;
	gboolean ret = FALSE;

	parts = pk_package_id_split (package_id);
	if (!parts)
		goto out;
	if (!click_pkid_data_is_click (parts[PK_PACKAGE_ID_DATA]))
		goto out;
	if (name)
		*name = g_strdup (parts[PK_PACKAGE_ID_NAME]);
	if (version)
		*version = g_strdup (parts[PK_PACKAGE_ID_VERSION]);
	if (architecture)
		*architecture = g_strdup (parts[PK_PACKAGE_ID_ARCH]);
	ret = TRUE;

out:
	g_strfreev (parts);
	return ret;
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
	gchar *click_stderr = NULL;
	gint click_status;
	JsonParser *parser = NULL;
	JsonObject *manifest;
	gchar *pkid = NULL;

	argv = g_malloc0_n (6, sizeof (*argv));
	i = 0;
	argv[i++] = g_strdup ("click");
	argv[i++] = g_strdup ("install");
	username = click_get_username_for_uid
		(pk_transaction_get_uid (transaction));
	if (username)
		argv[i++] = g_strdup_printf ("--user=%s", username);
	/* TODO: make --force-missing-framework configurable */
	argv[i++] = g_strdup (filename);
	envp = click_get_envp ();
	ret = g_spawn_sync (NULL, argv, envp,
			    G_SPAWN_SEARCH_PATH | G_SPAWN_STDOUT_TO_DEV_NULL,
			    NULL, NULL, NULL, &click_stderr, &click_status,
			    NULL);
	if (!ret)
		goto out;
	if (!g_spawn_check_exit_status (click_status, NULL)) {
		gchar *summary = g_strdup_printf ("%s failed to install.",
						  filename);
		click_pk_error (plugin,
				PK_ERROR_ENUM_PACKAGE_FAILED_TO_INSTALL,
				summary, click_stderr);
		g_free (summary);
		ret = FALSE;
		goto out;
	}

	parser = click_get_manifest (plugin, filename);
	if (parser) {
		manifest = json_node_get_object
			(json_parser_get_root (parser));
		pkid = click_build_pkid (plugin, manifest, "installed:click");
	}
	if (!pk_backend_job_get_is_error_set (plugin->job)) {
		pk_backend_job_package (plugin->job, PK_INFO_ENUM_INSTALLED,
					pkid, "summary goes here");
		ret = TRUE;
	}

out:
	g_strfreev (argv);
	g_free (username);
	g_strfreev (envp);
	g_free (click_stderr);
	g_clear_object (&parser);
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
	const gchar *title = NULL;
	gchar *pkid = NULL;

	plugin = (PkPlugin *) data;
	manifest = json_node_get_object (element_node);
	if (!manifest)
		return;
	if (json_object_has_member (manifest, "title"))
		title = json_object_get_string_member (manifest, "title");
	if (!title)
		title = "";

	pkid = click_build_pkid (plugin, manifest, "installed:click");
	if (pkid)
		pk_backend_job_package (plugin->job, PK_INFO_ENUM_INSTALLED,
					pkid, title);

	g_free (pkid);
}

static void
click_get_packages (PkPlugin *plugin, PkTransaction *transaction)
{
	JsonArray *array = NULL;

	array = click_get_list (plugin, transaction);
	if (!array)
		return;
	json_array_foreach_element (array, click_get_packages_one, plugin);
	json_array_unref (array);
}

static gboolean
click_remove_package (PkPlugin *plugin, PkTransaction *transaction,
		      const gchar *package_id)
{
	gboolean ret = FALSE;
	gchar *username = NULL;
	gchar *name = NULL;
	gchar *version = NULL;
	ClickDB *db = NULL;
	ClickUser *registry = NULL;
	gchar *old_version = NULL;
	GError *error = NULL;
	gchar *summary = NULL;

	username = click_get_username_for_uid
		(pk_transaction_get_uid (transaction));
	if (!username) {
		g_error ("Click: cannot remove packages without a username");
		goto out;
	}
	if (!click_split_pkid (package_id, &name, &version, NULL)) {
		g_error ("Click: cannot parse package ID '%s'", package_id);
		goto out;
	}
	db = click_db_new ();
	click_db_read (db, NULL, &error);
	if (error) {
		summary = g_strdup_printf
			("Unable to read Click database while removing %s.",
			 package_id);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, error->message);
		goto out;
	}
	registry = click_user_new_for_user (db, username, &error);
	if (error) {
		summary = g_strdup_printf
			("Unable to read Click database while removing %s.",
			 package_id);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, error->message);
		goto out;
	}
	old_version = click_user_get_version (registry, name, &error);
	if (error) {
		summary = g_strdup_printf
			("Unable to get current version of Click package %s.",
			 name);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, error->message);
		goto out;
	}
	if (strcmp (old_version, version) != 0) {
		summary = g_strdup_printf
			("Not removing Click package %s %s; does not match "
			 "current version %s.", name, version, old_version);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, NULL);
		goto out;
	}
	click_user_remove (registry, name, &error);
	if (error) {
		summary = g_strdup_printf ("Failed to remove %s.", package_id);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, error->message);
		goto out;
	}
	click_db_maybe_remove (db, name, version, &error);
	if (error) {
		summary = g_strdup_printf ("Failed to remove %s.", package_id);
		click_pk_error (plugin, PK_ERROR_ENUM_PACKAGE_FAILED_TO_REMOVE,
				summary, error->message);
		goto out;
	}
	/* TODO: remove data? */
	ret = TRUE;

out:
	g_free (summary);
	if (error)
		g_error_free (error);
	g_free (old_version);
	g_object_unref (registry);
	g_object_unref (db);
	g_free (version);
	g_free (name);
	g_free (username);

	return ret;
}

static void
click_remove_packages (PkPlugin *plugin, PkTransaction *transaction,
		       gchar **package_ids)
{
	gboolean ret = FALSE;
	gint i;

	for (i = 0; package_ids[i]; ++i) {
		g_debug ("Click: removing %s", package_ids[i]);
		ret = click_remove_package (plugin, transaction,
					    package_ids[i]);
		if (!ret)
			break;
	}
}

struct click_search_data {
	PkPlugin *plugin;
	gchar **values;
	gboolean search_details;
};

static void
click_search_emit (PkPlugin *plugin, JsonObject *manifest, const gchar *title)
{
	gchar *package_id;

	package_id = click_build_pkid (plugin, manifest, "installed:click");
	if (!package_id)
		return;
	g_debug ("Found package: %s", package_id);
	pk_backend_job_package (plugin->job, PK_INFO_ENUM_INSTALLED,
				package_id, title);

	g_free (package_id);
}

static void
click_search_one (JsonArray *array, guint index, JsonNode *element_node,
		  gpointer vdata)
{
	struct click_search_data *data;
	JsonObject *manifest;
	const gchar *name = NULL;
	const gchar *title = NULL;
	const gchar *description = NULL;
	gchar **value;

	data = (struct click_search_data *) vdata;
	manifest = json_node_get_object (element_node);
	if (!manifest)
		return;
	name = json_object_get_string_member (manifest, "name");
	if (!name)
		return;
	if (data->search_details && json_object_has_member (manifest, "title"))
		title = json_object_get_string_member (manifest, "title");
	if (!title)
		title = "";
	if (data->search_details &&
	    json_object_has_member (manifest, "description"))
		description = json_object_get_string_member (manifest,
							     "description");
	if (!description)
		description = "";

	for (value = data->values; *value; ++value) {
		if (strcasestr (name, *value)) {
			click_search_emit (data->plugin, manifest, title);
			break;
		}
		if (data->search_details &&
		    (strcasestr (title, *value) ||
		     strcasestr (description, *value))) {
			click_search_emit (data->plugin, manifest, title);
			break;
		}
	}
}

static void
click_search (PkPlugin *plugin, PkTransaction *transaction, gchar **values,
	      gboolean search_details)
{
	JsonArray *array = NULL;
	struct click_search_data data;

	array = click_get_list (plugin, transaction);
	if (!array)
		return;
	data.plugin = plugin;
	data.values = values;
	data.search_details = search_details;
	json_array_foreach_element (array, click_search_one, &data);
	json_array_unref (array);
}

static void
click_skip_native_backend (PkPlugin *plugin)
{
	if (!pk_backend_job_get_is_error_set (plugin->job))
		pk_backend_job_set_exit_code (plugin->job,
					      PK_EXIT_ENUM_SKIP_TRANSACTION);
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
	pk_backend_implement (plugin->backend, PK_ROLE_ENUM_INSTALL_FILES);
	pk_backend_implement (plugin->backend, PK_ROLE_ENUM_GET_PACKAGES);
	pk_backend_implement (plugin->backend, PK_ROLE_ENUM_REMOVE_PACKAGES);
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
	gchar **package_ids = NULL;
	gchar **click_data = NULL;
	gchar **values;
	PkBitfield flags;
	gboolean simulating;

	g_debug ("Processing transaction");

	pk_backend_job_reset (plugin->job);
	pk_transaction_signals_reset (transaction, plugin->job);
	pk_backend_job_set_status (plugin->job, PK_STATUS_ENUM_SETUP);

	role = pk_transaction_get_role (transaction);

	flags = pk_transaction_get_transaction_flags (transaction);
	simulating = pk_bitfield_contain (flags,
					  PK_TRANSACTION_FLAG_ENUM_SIMULATE);

	switch (role) {
		case PK_ROLE_ENUM_INSTALL_FILES:
			/* TODO: Simulation needs to be smarter - backend
			 * needs to Simulate() with remaining packages.
			 */
			full_paths = pk_transaction_get_full_paths
				(transaction);
			click_data = click_filter_click_files (transaction,
							       full_paths);
			if (!simulating && click_data)
				click_install_files (plugin, transaction,
						     click_data);

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

		case PK_ROLE_ENUM_REMOVE_PACKAGES:
			package_ids = pk_transaction_get_package_ids
				(transaction);
			click_data = click_filter_click_packages (transaction,
								  package_ids);
			if (!simulating && click_data)
				click_remove_packages (plugin, transaction,
						       click_data);

			package_ids = pk_transaction_get_package_ids
				(transaction);
			if (g_strv_length (package_ids) == 0)
				click_skip_native_backend (plugin);
			break;

		case PK_ROLE_ENUM_SEARCH_NAME:
		case PK_ROLE_ENUM_SEARCH_DETAILS:
			values = pk_transaction_get_values (transaction);
			click_search (plugin, transaction, values,
				      role == PK_ROLE_ENUM_SEARCH_DETAILS);
			break;

		default:
			break;
	}

	g_strfreev (click_data);
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
	const gchar *remove_action =
		"org.freedesktop.packagekit.package-remove";
	const gchar **install_action;
	gchar **full_paths;
	gchar **package_ids;
	gint i;

	if (!action_id)
		return NULL;

	for (install_action = install_actions; *install_action;
	     ++install_action) {
		if (strcmp (action_id, *install_action) == 0) {
			/* Use an action with weaker auth requirements if
			 * and only if all the packages in the list are
			 * Click files.
			 */
			full_paths = pk_transaction_get_full_paths
				(transaction);
			for (i = 0; full_paths[i]; ++i) {
				if (!click_is_click_file (full_paths[i]))
					break;
			}
			if (!full_paths[i])
				return "com.ubuntu.click.package-install";
		}
	}

	if (strcmp (action_id, remove_action) == 0) {
		/* Use an action with weaker auth requirements if and only
		 * if all the packages in the list are Click packages.
		 */
		package_ids = pk_transaction_get_package_ids
			(transaction);
		for (i = 0; package_ids[i]; ++i) {
			if (!click_is_click_package (package_ids[i]))
				break;
		}
		if (!package_ids[i])
			return "com.ubuntu.click.package-remove";
	}

	return action_id;
}
