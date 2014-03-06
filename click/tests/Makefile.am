noinst_DATA = preload.gir
CLEANFILES = $(noinst_DATA)

preload.gir: preload.h
	PKG_CONFIG_PATH=$(top_builddir)/lib/click g-ir-scanner \
		-n preload --nsversion 0 -l c \
		--pkg glib-2.0 --pkg gee-0.8 --pkg click-0.4 \
		-I$(top_builddir)/lib/click -L$(top_builddir)/lib/click \
		--accept-unprefixed --warn-all \
		$< --output $@
