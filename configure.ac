AC_INIT([click], [0.1], [https://launchpad.net/click])
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

AC_CONFIG_FILES([
	Makefile
	click/Makefile
	preload/Makefile
	])
AC_OUTPUT
