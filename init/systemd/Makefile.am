EXTRA_DIST = click-system-hooks.service.in click-user-hooks.service.in

CLEANFILES = click-system-hooks.service click-user-hooks.service

if INSTALL_SYSTEMD
nodist_systemdsystemunit_DATA = click-system-hooks.service
nodist_systemduserunit_DATA = click-user-hooks.service

%.service: %.service.in
	sed -e "s,[@]bindir[@],$(bindir),g" $< > $@
endif
