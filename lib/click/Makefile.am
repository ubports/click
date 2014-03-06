AM_CPPFLAGS = \
	-I. \
	-D_GNU_SOURCE
AM_CFLAGS = \
	$(LIBCLICK_CFLAGS) \
	$(VALA_CFLAGS) \
	-Wno-unused-but-set-variable \
	-Wno-unused-function \
	-Wno-unused-variable
VALAC = $(srcdir)/valac-wrapper
AM_VALAFLAGS = \
	-H click.h \
	--gir Click-0.4.gir \
	--library click-0.4 \
	--pkg posix \
	--pkg gee-0.8 \
	--pkg json-glib-1.0 \
	--target-glib 2.32

lib_LTLIBRARIES = libclick-0.4.la

libclick_0_4_la_SOURCES = \
	database.vala \
	hooks.vala \
	osextras.vala \
	paths.vala \
	posix-extra.vapi \
	query.vala \
	user.vala

EXTRA_libclick_0_4_la_DEPENDENCIES = \
	click.sym

HEADER_FILES = \
	click.h

BUILT_SOURCES = paths.vala

CLEANFILES = \
	$(BUILT_SOURCES) \
	$(HEADER_FILES) \
	libclick_0_4_la_vala.stamp \
	click.h \
	database.c \
	hooks.c \
	osextras.c \
	paths.c \
	query.c \
	user.c

do_subst = sed \
	-e 's,[@]sysconfdir[@],$(sysconfdir),g' \
	-e 's,[@]pkgdatadir[@],$(pkgdatadir),g'

paths.vala: paths.vala.in Makefile
	$(do_subst) < $(srcdir)/paths.vala.in > $@

includeclickdir = $(includedir)/click-0.4
includeclick_HEADERS = \
	$(HEADER_FILES)

libclick_0_4_la_LIBADD = $(LIBCLICK_LIBS)

libclick_0_4_la_LDFLAGS = \
	-export-dynamic \
	-export-symbols $(srcdir)/click.sym \
	-version-info 4:0:4

EXTRA_DIST = click-0.4.pc.in

pkgconfigdir = $(libdir)/pkgconfig
pkgconfig_DATA = click-0.4.pc

INTROSPECTION_COMPILER_ARGS = \
	--includedir $(srcdir) \
	--includedir $(builddir) \
	--shared-library libclick-0.4.so.0

girdir = $(datadir)/gir-1.0
gir_DATA = Click-0.4.gir

typelibdir = $(libdir)/girepository-1.0
typelib_DATA = Click-0.4.typelib

# We intentionally don't install a VAPI at this point; libclick is written
# in Vala for implementation convenience, but this probably won't be
# appropriate for most of its clients.  The intent is that the C API is
# canonical (with its reflections via gobject-introspection).
#vapidir = $(VAPIGEN_VAPIDIR)
#vapi_DATA = click-0.4.vapi
noinst_DATA = click-0.4.vapi

CLEANFILES += $(gir_DATA) $(typelib_DATA) $(noinst_DATA)

$(HEADER_FILES) $(gir_DATA) $(noinst_DATA): libclick_0_4_la_vala.stamp

%.typelib: %.gir
	$(INTROSPECTION_COMPILER) $(INTROSPECTION_COMPILER_ARGS) $< -o $@
