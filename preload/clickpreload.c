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
#include <string.h>
#include <sys/types.h>
#include <unistd.h>

static int (*libc_chown) (const char *, uid_t, gid_t) = (void *) 0;
static int (*libc_execvp) (const char *, char * const []) = (void *) 0;
static int (*libc_fchown) (int, uid_t, gid_t) = (void *) 0;

uid_t euid;

void __attribute__ ((constructor)) clickpreload_init (void)
{
    libc_chown = dlsym (RTLD_NEXT, "chown");
    if (!libc_chown || dlerror ())
        _exit (1);
    libc_execvp = dlsym (RTLD_NEXT, "execvp");
    if (!libc_execvp || dlerror ())
        _exit (1);
    libc_fchown = dlsym (RTLD_NEXT, "fchown");
    if (!libc_fchown || dlerror ())
        _exit (1);

    euid = geteuid ();
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
 */
int fsync (int fd)
{
    return 0;
}

int sync_file_range(int fd, off64_t offset, off64_t nbytes, unsigned int flags)
{
    return 0;
}
