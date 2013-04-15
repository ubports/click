/* Copyright (C) 2013 Canonical Ltd.
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

/* Stub out a few syscalls that are unhelpful when installing Click
 * packages.  This is roughly akin to the effect of using all of fakechroot,
 * fakeroot, and eatmydata, but a few orders of magnitude simpler.
 */

#define _GNU_SOURCE

#include <dlfcn.h>
#include <fcntl.h>
#include <grp.h>
#include <pwd.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static int (*libc_chown) (const char *, uid_t, gid_t) = (void *) 0;
static int (*libc_execvp) (const char *, char * const []) = (void *) 0;
static int (*libc_fchown) (int, uid_t, gid_t) = (void *) 0;
static struct group *(*libc_getgrnam) (const char *) = (void *) 0;
static struct passwd *(*libc_getpwnam) (const char *) = (void *) 0;

uid_t euid;
struct passwd root_pwd;
struct group root_grp;

#define GET_NEXT_SYMBOL(name) \
    do { \
        libc_##name = dlsym (RTLD_NEXT, #name); \
        if (!libc_##name || dlerror ()) \
            _exit (1); \
    } while (0)

void __attribute__ ((constructor)) clickpreload_init (void)
{
    /* Clear any old error conditions, albeit unlikely, as per dlsym(2) */
    dlerror ();

    GET_NEXT_SYMBOL (chown);
    GET_NEXT_SYMBOL (execvp);
    GET_NEXT_SYMBOL (fchown);
    GET_NEXT_SYMBOL (getgrnam);
    GET_NEXT_SYMBOL (getpwnam);

    euid = geteuid ();
    /* dpkg only cares about these fields. */
    root_pwd.pw_uid = 0;
    root_grp.gr_gid = 0;
}

/* dpkg calls chown/fchown to set permissions of extracted files.  If we
 * aren't running as root, we don't care.
 */
int chown (const char *path, uid_t owner, gid_t group)
{
    if (euid != 0)
        return 0;

    if (!libc_chown)
        clickpreload_init ();
    return (*libc_chown) (path, owner, group);
}

int fchown (int fd, uid_t owner, gid_t group)
{
    if (euid != 0)
        return 0;

    if (!libc_fchown)
        clickpreload_init ();
    return (*libc_fchown) (fd, owner, group);
}

/* Similarly, we don't much care about passwd/group lookups when we aren't
 * root.  (This could be more sanely replaced by having dpkg cache those
 * lookups itself.)
 */
struct passwd *getpwnam (const char *name)
{
    if (!libc_getpwnam)
        clickpreload_init ();  /* also needed for root_pwd */

    if (euid != 0)
        return &root_pwd;
    return (*libc_getpwnam) (name);
}

struct group *getgrnam (const char *name)
{
    if (!libc_getgrnam)
        clickpreload_init ();  /* also needed for root_grp */

    if (euid != 0)
        return &root_grp;
    return (*libc_getgrnam) (name);
}

/* dpkg calls chroot to run maintainer scripts when --instdir is used (which
 * we use so that we can have independently-rooted filesystem tarballs).
 * However, there is exactly one maintainer script ever used by Click
 * packages, and that's a static preinst which doesn't touch the filesystem
 * except to be executed with /bin/sh.  Chrooting for this causes more
 * problems than it solves.
 */
int chroot (const char *path)
{
    return 0;
}

/* dpkg executes the static preinst.  We don't want it. */
int execvp (const char *file, char * const argv[])
{
    if (strcmp (file, "/.click/tmp.ci/preinst") == 0)
        _exit (0);
    return (*libc_execvp) (file, argv);
}

/* dpkg calls fsync/sync_file_range quite a lot.  However, Click packages
 * never correspond to essential system facilities, so it's OK to compromise
 * perfect write reliability in the face of hostile filesystem
 * implementations for performance.
 *
 * (Note that dpkg only started using fsync/sync_file_range relatively
 * recently, and on many reasonable filesystem configurations using those
 * functions buys us nothing; most of dpkg's reliability comes from other
 * strategies, such as careful unpack and renaming into place.)
 */
int fsync (int fd)
{
    return 0;
}

int sync_file_range(int fd, off64_t offset, off64_t nbytes, unsigned int flags)
{
    return 0;
}
