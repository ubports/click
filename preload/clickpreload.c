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

#include <assert.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <grp.h>
#include <pwd.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static int (*libc_chmod) (const char *, mode_t) = (void *) 0;
static int (*libc_chown) (const char *, uid_t, gid_t) = (void *) 0;
static int (*libc_execvp) (const char *, char * const []) = (void *) 0;
static int (*libc_fchmod) (int, mode_t) = (void *) 0;
static int (*libc_fchown) (int, uid_t, gid_t) = (void *) 0;
static FILE *(*libc_fopen) (const char *, const char *) = (void *) 0;
static FILE *(*libc_fopen64) (const char *, const char *) = (void *) 0;
static struct group *(*libc_getgrnam) (const char *) = (void *) 0;
static struct passwd *(*libc_getpwnam) (const char *) = (void *) 0;
static int (*libc_lchown) (const char *, uid_t, gid_t) = (void *) 0;
static int (*libc_link) (const char *, const char *) = (void *) 0;
static int (*libc_mkdir) (const char *, mode_t) = (void *) 0;
static int (*libc_mkfifo) (const char *, mode_t) = (void *) 0;
static int (*libc_mknod) (const char *, mode_t, dev_t) = (void *) 0;
static int (*libc_open) (const char *, int, mode_t) = (void *) 0;
static int (*libc_open64) (const char *, int, mode_t) = (void *) 0;
static int (*libc_symlink) (const char *, const char *) = (void *) 0;
static int (*libc___xstat) (int, const char *, struct stat *) = (void *) 0;
static int (*libc___xstat64) (int, const char *, struct stat64 *) = (void *) 0;

uid_t euid;
struct passwd root_pwd;
struct group root_grp;
const char *base_path;
size_t base_path_len;
const char *package_path;
int package_fd;

#define GET_NEXT_SYMBOL(name) \
    do { \
        libc_##name = dlsym (RTLD_NEXT, #name); \
        if (dlerror ()) \
            _exit (1); \
    } while (0)

static void __attribute__ ((constructor)) clickpreload_init (void)
{
    const char *package_fd_str;

    /* Clear any old error conditions, albeit unlikely, as per dlsym(2) */
    dlerror ();

    GET_NEXT_SYMBOL (chmod);
    GET_NEXT_SYMBOL (chown);
    GET_NEXT_SYMBOL (execvp);
    GET_NEXT_SYMBOL (fchmod);
    GET_NEXT_SYMBOL (fchown);
    GET_NEXT_SYMBOL (fopen);
    GET_NEXT_SYMBOL (fopen64);
    GET_NEXT_SYMBOL (getgrnam);
    GET_NEXT_SYMBOL (getpwnam);
    GET_NEXT_SYMBOL (lchown);
    GET_NEXT_SYMBOL (link);
    GET_NEXT_SYMBOL (mkdir);
    GET_NEXT_SYMBOL (mkfifo);
    GET_NEXT_SYMBOL (mknod);
    GET_NEXT_SYMBOL (open);
    GET_NEXT_SYMBOL (open64);
    GET_NEXT_SYMBOL (symlink);
    GET_NEXT_SYMBOL (__xstat);
    GET_NEXT_SYMBOL (__xstat64);

    euid = geteuid ();
    /* dpkg only cares about these fields. */
    root_pwd.pw_uid = 0;
    root_grp.gr_gid = 0;

    base_path = getenv ("CLICK_BASE_DIR");
    base_path_len = base_path ? strlen (base_path) : 0;

    package_path = getenv ("CLICK_PACKAGE_PATH");
    package_fd_str = getenv ("CLICK_PACKAGE_FD");
    package_fd = atoi (package_fd_str);
}

/* dpkg calls chown/fchown/lchown to set permissions of extracted files.  If
 * we aren't running as root, we don't care.
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

int lchown (const char *path, uid_t owner, gid_t group)
{
    if (euid != 0)
        return 0;

    if (!libc_lchown)
        clickpreload_init ();
    return (*libc_lchown) (path, owner, group);
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

    if (!libc_execvp)
        clickpreload_init ();
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

/* Sandboxing:
 *
 * We try to insulate against dpkg getting confused enough by malformed
 * archives to write outside the instdir.  This is not full confinement, and
 * generally for system security it should be sufficient to run "click
 * install" as a specialised user; as such we don't necessarily wrap all
 * possible relevant functions here.  The main purpose of this is just to
 * provide a useful error message if dpkg gets confused.
 */

static void clickpreload_assert_path_in_instdir (const char *verb,
                                                 const char *pathname)
{
    if (strncmp (pathname, base_path, base_path_len) == 0 &&
        (pathname[base_path_len] == '\0' || pathname[base_path_len] == '/'))
        return;

    /* When building click in a chroot with pkgbinarymangler, dpkg-deb is in
     * fact a wrapper shell script, and bash checks at startup whether it
     * can open /dev/tty for writing.  This is harmless, so allow it.
     */
    if (strcmp (verb, "write-open") == 0 && strcmp (pathname, "/dev/tty") == 0)
        return;

    fprintf (stderr,
             "Sandbox failure: 'click install' not permitted to %s '%s'\n",
             verb, pathname);
    exit (1);
}

int link (const char *oldpath, const char *newpath)
{
    if (!libc_link)
        clickpreload_init ();  /* also needed for base_path, base_path_len */

    clickpreload_assert_path_in_instdir ("make hard link", newpath);
    return (*libc_link) (oldpath, newpath);
}

int mkdir (const char *pathname, mode_t mode)
{
    if (!libc_mkdir)
        clickpreload_init ();  /* also needed for base_path, base_path_len */

    clickpreload_assert_path_in_instdir ("mkdir", pathname);
    return (*libc_mkdir) (pathname, mode);
}

int mkfifo (const char *pathname, mode_t mode)
{
    if (!libc_mkfifo)
        clickpreload_init ();  /* also needed for base_path, base_path_len */

    clickpreload_assert_path_in_instdir ("mkfifo", pathname);
    return (*libc_mkfifo) (pathname, mode);
}

int mknod (const char *pathname, mode_t mode, dev_t dev)
{
    if (!libc_mknod)
        clickpreload_init ();  /* also needed for base_path, base_path_len */

    clickpreload_assert_path_in_instdir ("mknod", pathname);
    return (*libc_mknod) (pathname, mode, dev);
}

int symlink (const char *oldpath, const char *newpath)
{
    if (!libc_symlink)
        clickpreload_init ();  /* also needed for base_path, base_path_len */

    clickpreload_assert_path_in_instdir ("make symbolic link", newpath);
    return (*libc_symlink) (oldpath, newpath);
}

/* As well as write sandboxing, our versions of fopen, open, and stat also
 * trap accesses to the package path and turn them into accesses to a fixed
 * file descriptor instead.  With some cooperation from click.install, this
 * allows dpkg to read packages in paths not readable by the clickpkg user.
 *
 * We cannot do this entirely perfectly.  In particular, we have to seek to
 * the start of the file on open, but the file offset is shared among all
 * duplicates of a file descriptor.  Let's hope that dpkg doesn't open the
 * .deb multiple times and expect to have independent file offsets ...
 */

FILE *fopen (const char *pathname, const char *mode)
{
    int for_reading =
        (strncmp (mode, "r", 1) == 0 && strncmp (mode, "r+", 2) != 0);

    if (!libc_fopen)
        clickpreload_init ();  /* also needed for package_path */

    if (for_reading && package_path && strcmp (pathname, package_path) == 0) {
        int dup_fd = dup (package_fd);
        lseek (dup_fd, 0, SEEK_SET);  /* also changes offset of package_fd */
        return fdopen (dup_fd, mode);
    }

    if (!for_reading)
        clickpreload_assert_path_in_instdir ("write-fdopen", pathname);

    return (*libc_fopen) (pathname, mode);
}

FILE *fopen64 (const char *pathname, const char *mode)
{
    int for_reading =
        (strncmp (mode, "r", 1) == 0 && strncmp (mode, "r+", 2) != 0);

    if (!libc_fopen64)
        clickpreload_init ();  /* also needed for package_path */

    if (for_reading && package_path && strcmp (pathname, package_path) == 0) {
        int dup_fd = dup (package_fd);
        lseek (dup_fd, 0, SEEK_SET);  /* also changes offset of package_fd */
        return fdopen (dup_fd, mode);
    }

    if (!for_reading)
        clickpreload_assert_path_in_instdir ("write-fdopen", pathname);

    return (*libc_fopen64) (pathname, mode);
}

int open (const char *pathname, int flags, ...)
{
    int for_writing = ((flags & O_WRONLY) || (flags & O_RDWR));
    mode_t mode = 0;
    int ret;

    if (!libc_open)
        clickpreload_init ();  /* also needed for package_path */

    if (!for_writing && package_path && strcmp (pathname, package_path) == 0) {
        int dup_fd = dup (package_fd);
        lseek (dup_fd, 0, SEEK_SET);  /* also changes offset of package_fd */
        return dup_fd;
    }

    if (for_writing)
        clickpreload_assert_path_in_instdir ("write-open", pathname);

    if (flags & O_CREAT) {
        va_list argv;
        va_start (argv, flags);
        mode = va_arg (argv, mode_t);
        va_end (argv);
    }

    ret = (*libc_open) (pathname, flags, mode);
    return ret;
}

int open64 (const char *pathname, int flags, ...)
{
    int for_writing = ((flags & O_WRONLY) || (flags & O_RDWR));
    mode_t mode = 0;
    int ret;

    if (!libc_open64)
        clickpreload_init ();  /* also needed for package_path */

    if (!for_writing && package_path && strcmp (pathname, package_path) == 0) {
        int dup_fd = dup (package_fd);
        lseek (dup_fd, 0, SEEK_SET);  /* also changes offset of package_fd */
        return dup_fd;
    }

    if (for_writing)
        clickpreload_assert_path_in_instdir ("write-open", pathname);

    if (flags & O_CREAT) {
        va_list argv;
        va_start (argv, flags);
        mode = va_arg (argv, mode_t);
        va_end (argv);
    }

    ret = (*libc_open64) (pathname, flags, mode);
    return ret;
}

int __xstat (int ver, const char *pathname, struct stat *buf)
{
    if (!libc___xstat)
        clickpreload_init ();  /* also needed for package_path */

    if (package_path && strcmp (pathname, package_path) == 0)
        return __fxstat (ver, package_fd, buf);

    return (*libc___xstat) (ver, pathname, buf);
}

int __xstat64 (int ver, const char *pathname, struct stat64 *buf)
{
    if (!libc___xstat64)
        clickpreload_init ();  /* also needed for package_path */

    if (package_path && strcmp (pathname, package_path) == 0)
        return __fxstat64 (ver, package_fd, buf);

    return (*libc___xstat64) (ver, pathname, buf);
}

/* As well as write sandboxing, our versions of chmod and fchmod also
 * prevent the 0200 (u+w) permission bit from being removed from unpacked
 * files.  dpkg normally expects to be run as root which can override DAC
 * write permissions, so a mode 04xx file is not normally a problem for it,
 * but it is a problem when running dpkg as non-root.  Since unpacked
 * packages are non-writeable from the point of view of the package's code,
 * forcing u+w is safe.
 */

int chmod (const char *path, mode_t mode)
{
    if (!libc_chmod)
        clickpreload_init ();  /* also needed for package_path */

    clickpreload_assert_path_in_instdir ("chmod", path);
    mode |= S_IWUSR;
    return (*libc_chmod) (path, mode);
}

int fchmod (int fd, mode_t mode)
{
    if (!libc_fchmod)
        clickpreload_init ();

    mode |= S_IWUSR;
    return (*libc_fchmod) (fd, mode);
}
