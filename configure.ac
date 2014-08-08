AC_INIT([click],m4_esyscmd([./get-version]),[https://launchpad.net/click])
AC_CONFIG_SRCDIR([preload/clickpreload.c])
AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([foreign])
AM_CONFIG_HEADER([config.h])
AC_USE_SYSTEM_EXTENSIONS
LT_INIT([disable-static])

AC_SUBST([GETTEXT_PACKAGE], [click])
IT_PROG_INTLTOOL

AC_PROG_CC
CFLAGS="$CFLAGS -Wall"

AC_ARG_WITH([python-interpreters],
	[AS_HELP_STRING([--with-python-interpreters],
		[install for these Python interpreters (space-separated, default: python3)])],
	[PYTHON_INTERPRETERS="$withval"],
	[PYTHON_INTERPRETERS=python3])
AC_SUBST([PYTHON_INTERPRETERS])

AC_ARG_WITH([default-root],
	[AS_HELP_STRING([--with-default-root],
		[set default root path for installed packages (default: /opt/click.ubuntu.com)])],
	[DEFAULT_ROOT="$withval"],
	[DEFAULT_ROOT=/opt/click.ubuntu.com])
AC_SUBST([DEFAULT_ROOT])

click_save_LIBS="$LIBS"
AC_SEARCH_LIBS([dlopen], [dl])
AC_SUBST([PRELOAD_LIBS], ["$LIBS"])
LIBS="$click_save_LIBS"

AC_CACHE_CHECK([for Perl vendor library directory], [click_cv_perl_vendorlib],
	[click_cv_perl_vendorlib=`perl -MConfig -e 'print $Config{vendorlib}'`])
AC_SUBST([perl_vendorlib], ["$click_cv_perl_vendorlib"])

AM_PROG_VALAC
PKG_CHECK_MODULES([LIBCLICK], [
	glib-2.0 >= 2.34
	gobject-2.0 >= 2.34
	json-glib-1.0 >= 0.10
	gee-0.8
	])
AC_SUBST([LIBCLICK_CFLAGS])
AC_SUBST([LIBCLICK_LIBS])

# Structure characteristics needed for the Python/C integration in the test
# suite.
AC_COMPUTE_INT([STAT_OFFSET_UID], [offsetof(struct stat, st_uid)], [
	AC_INCLUDES_DEFAULT
	#include <sys/stat.h>
	])
AC_SUBST([STAT_OFFSET_UID])
AC_COMPUTE_INT([STAT_OFFSET_GID], [offsetof(struct stat, st_gid)], [
	AC_INCLUDES_DEFAULT
	#include <sys/stat.h>
	])
AC_SUBST([STAT_OFFSET_GID])
AC_COMPUTE_INT([STAT64_OFFSET_UID], [offsetof(struct stat64, st_uid)], [
	AC_INCLUDES_DEFAULT
	#include <sys/stat.h>
	])
AC_SUBST([STAT64_OFFSET_UID])
AC_COMPUTE_INT([STAT64_OFFSET_GID], [offsetof(struct stat64, st_gid)], [
	AC_INCLUDES_DEFAULT
	#include <sys/stat.h>
	])
AC_SUBST([STAT64_OFFSET_GID])

GOBJECT_INTROSPECTION_REQUIRE([0.6.7])
VAPIGEN_VAPIDIR=`$PKG_CONFIG --variable=vapidir vapigen`
AC_SUBST([VAPIGEN_VAPIDIR])

AC_ARG_ENABLE([packagekit],
	AS_HELP_STRING([--disable-packagekit], [disable PackageKit plugin]),
	[], [enable_packagekit=yes])
if test "x$enable_packagekit" = xyes; then
	PKG_CHECK_MODULES([PKPLUGIN], [
		gio-2.0
		glib-2.0 >= 2.34
		gobject-2.0 >= 2.28
		json-glib-1.0 >= 0.10
		packagekit-plugin >= 0.8.10
		])
	AC_SUBST([PKPLUGIN_CFLAGS])
	AC_SUBST([PKPLUGIN_LIBS])
	AC_CACHE_CHECK([for packagekit-plugin library directory],
		[click_cv_pkpluginlibdir],
		[click_cv_pkpluginlibdir=`$PKG_CONFIG --variable=libdir packagekit-plugin`])
	AC_SUBST([pkpluginlibdir], ["$click_cv_pkpluginlibdir"])
fi
AM_CONDITIONAL([PACKAGEKIT], [test "x$enable_packagekit" = xyes])

AC_ARG_ENABLE([systemd],
	      AS_HELP_STRING([--disable-systemd], [Disable systemd integration]))
AM_CONDITIONAL([INSTALL_SYSTEMD], [test "x$enable_systemd" != xno])

AC_ARG_WITH([systemdsystemunitdir],
	    AS_HELP_STRING([--with-systemdsystemunitdir=DIR], [Directory for systemd system unit files]))
if test "x$enable_systemd" != xno && test "x$with_systemdsystemunitdir" = x; then
	AC_MSG_CHECKING([for systemd system unit directory])
	with_systemdsystemunitdir="$($PKG_CONFIG --variable=systemdsystemunitdir systemd)"
	if test "x$with_systemdsystemunitdir" = x; then
		AC_MSG_ERROR([no systemd system unit directory found])
	fi
	AC_MSG_RESULT([$with_systemdsystemunitdir])
fi
AC_SUBST([systemdsystemunitdir], [$with_systemdsystemunitdir])

AC_ARG_WITH([systemduserunitdir],
	    AS_HELP_STRING([--with-systemduserunitdir=DIR], [Directory for systemd user unit files]))
if test "x$enable_systemd" != xno && test "x$with_systemduserunitdir" = x; then
	AC_MSG_CHECKING([for systemd user unit directory])
	with_systemduserunitdir="$($PKG_CONFIG --variable=systemduserunitdir systemd)"
	if test "x$with_systemduserunitdir" = x; then
		AC_MSG_ERROR([no systemd user unit directory found])
	fi
	AC_MSG_RESULT([$with_systemduserunitdir])
fi
AC_SUBST([systemduserunitdir], [$with_systemduserunitdir])

m4_include([m4/gcov.m4])
AC_TDD_GCOV
AM_CONDITIONAL([HAVE_GCOV], [test "x$ac_cv_check_gcov" = xyes])
AM_CONDITIONAL([HAVE_LCOV], [test "x$ac_cv_check_lcov" = xyes])
AM_CONDITIONAL([HAVE_GCOVR], [test "x$ac_cv_check_gcovr" = xyes])
AC_SUBST(COVERAGE_CFLAGS)
AC_SUBST(COVERAGE_LDFLAGS)

AC_CONFIG_FILES([
	Makefile
	click/Makefile
	click/tests/Makefile
	click/tests/config.py
	conf/Makefile
	conf/databases/Makefile
	conf/databases/99_default.conf
	debhelper/Makefile
	init/Makefile
	init/systemd/Makefile
	init/upstart/Makefile
	lib/Makefile
	lib/click/Makefile
	lib/click/click-0.4.pc
	pk-plugin/Makefile
	po/Makefile.in
	preload/Makefile
	schroot/Makefile
	])
AC_CONFIG_FILES([lib/click/valac-wrapper], [chmod +x lib/click/valac-wrapper])
AC_CONFIG_FILES([setup.py], [chmod +x setup.py])
AC_OUTPUT
