AC_INIT([click],
	m4_esyscmd_s([head -n1 debian/changelog | sed -n 's/.*(\(.*\)).*/\1/p']),
	[https://launchpad.net/click])
AC_CONFIG_SRCDIR([preload/clickpreload.c])
AC_CONFIG_MACRO_DIR([m4])
AM_INIT_AUTOMAKE([foreign])
AM_CONFIG_HEADER([config.h])
LT_INIT([disable-static])

AC_PROG_CC
CFLAGS="$CFLAGS -Wall"

click_save_LIBS="$LIBS"
AC_SEARCH_LIBS([dlopen], [dl])
AC_SUBST([PRELOAD_LIBS], ["$LIBS"])
LIBS="$click_save_LIBS"

AC_CACHE_CHECK([for Perl vendor library directory], [click_cv_perl_vendorlib],
	[click_cv_perl_vendorlib=`perl -MConfig -e 'print $Config{vendorlib}'`])
AC_SUBST([perl_vendorlib], ["$click_cv_perl_vendorlib"])

AC_CONFIG_FILES([
	Makefile
	click/Makefile
	debhelper/Makefile
	preload/Makefile
	])
AC_CONFIG_FILES([setup.py], [chmod +x setup.py])
AC_OUTPUT
