noinst_SCRIPTS = paths.py
CLEANFILES = $(noinst_SCRIPTS)

do_subst = sed \
	-e 's,[@]pkglibdir[@],$(pkglibdir),g' \
	-e 's,[@]DEFAULT_ROOT[@],$(DEFAULT_ROOT),g'

paths.py: paths.py.in Makefile
	$(do_subst) < $(srcdir)/paths.py.in > $@
