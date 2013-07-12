noinst_SCRIPTS = paths.py
CLEANFILES = $(noinst_SCRIPTS)

paths.py: paths.py.in Makefile
	sed -e 's,[@]pkglibdir[@],$(pkglibdir),g' < $(srcdir)/paths.py.in > $@
