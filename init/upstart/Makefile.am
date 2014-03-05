EXTRA_DIST = click-system-hooks.conf.in click-user-hooks.conf.in

CLEANFILES = click-system-hooks.conf click-user-hooks.conf

systemdir = $(sysconfdir)/init
sessionsdir = $(prefix)/share/upstart/sessions

system_DATA = click-system-hooks.conf
sessions_DATA = click-user-hooks.conf

%.conf: %.conf.in
	sed -e "s,[@]bindir[@],$(bindir),g" $< > $@
