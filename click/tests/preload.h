#include <sys/stat.h>
#include <sys/types.h>

#include <glib.h>

#include "click.h"

/**
 * chown:
 *
 * Attributes: (headers unistd.h)
 */
extern int chown (const char *file, uid_t owner, gid_t group);

/* Workaround for g-ir-scanner not picking up the type properly: mode_t is
 * uint32_t on all glibc platforms.
 */
/**
 * mkdir:
 * @mode: (type guint32)
 *
 * Attributes: (headers sys/stat.h,sys/types.h)
 */
extern int mkdir (const char *pathname, mode_t mode);

/**
 * getpwnam:
 *
 * Attributes: (headers sys/types.h,pwd.h)
 * Returns: (transfer none):
 */
extern struct passwd *getpwnam (const char *name);

/**
 * under_under_xstat:
 *
 * Attributes: (headers sys/types.h,sys/stat.h,unistd.h)
 */
extern int under_under_xstat (int ver, const char *pathname, struct stat *buf);

/**
 * under_under_xstat64:
 *
 * Attributes: (headers sys/types.h,sys/stat.h,unistd.h)
 */
extern int under_under_xstat64 (int ver, const char *pathname, struct stat64 *buf);

const gchar *g_get_user_name (void);

/**
 * g_spawn_sync:
 * @argv: (array zero-terminated=1):
 * @envp: (array zero-terminated=1):
 * @flags: (type gint)
 * @child_setup: (type gpointer)
 * @standard_output: (out) (array zero-terminated=1) (element-type guint8):
 * @standard_error: (out) (array zero-terminated=1) (element-type guint8):
 * @exit_status: (out):
 *
 * Attributes: (headers glib.h)
 */
gboolean g_spawn_sync         (const gchar          *working_directory,
                               gchar               **argv,
                               gchar               **envp,
                               GSpawnFlags           flags,
                               GSpawnChildSetupFunc  child_setup,
                               gpointer              user_data,
                               gchar               **standard_output,
                               gchar               **standard_error,
                               gint                 *exit_status,
                               GError              **error);

/**
 * click_find_on_path:
 *
 * Attributes: (headers glib.h)
 */
gboolean click_find_on_path (const gchar *command);

/**
 * click_get_db_dir:
 *
 * Attributes: (headers glib.h)
 */
gchar *click_get_db_dir (void);

/**
 * click_get_frameworks_dir:
 *
 * Attributes: (headers glib.h)
 */
gchar *click_get_frameworks_dir (void);

/**
 * click_get_hooks_dir:
 *
 * Attributes: (headers glib.h)
 */
gchar *click_get_hooks_dir (void);

/**
 * click_get_user_home:
 *
 * Attributes: (headers glib.h)
 */
gchar *click_get_user_home (const gchar *user_name);

/**
 * click_package_install_hooks:
 * @db: (type gpointer)
 *
 * Attributes: (headers glib.h,click.h)
 */
void click_package_install_hooks (ClickDB *db, const gchar *package,
				  const gchar *old_version,
				  const gchar *new_version,
				  const gchar *user_name, GError **error);
