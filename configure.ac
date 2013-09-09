AC_INIT([click],
	m4_esyscmd_s([head -n1 debian/changelog | sed -n 's/.*(\(.*\)).*/\1/p']),
	[https://launchpad.net/click])
AC_CONFIG_SRCDIR([preload/clickpreload.c])
AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([foreign])
AM_CONFIG_HEADER([config.h])
LT_INIT([disable-static])

AM_GNU_GETTEXT([external])
AM_GNU_GETTEXT_VERSION([0.18.1])
AC_SUBST([GETTEXT_PACKAGE], [click])
IT_PROG_INTLTOOL

AC_PROG_CC
CFLAGS="$CFLAGS -Wall"

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

AC_CONFIG_FILES([
	Makefile
	click/Makefile
	conf/Makefile
	conf/databases/Makefile
	conf/databases/99_default.conf
	debhelper/Makefile
	pk-plugin/Makefile
	po/Makefile.in
	preload/Makefile
	upstart/Makefile
	])
AC_CONFIG_FILES([setup.py], [chmod +x setup.py])
AC_OUTPUT
