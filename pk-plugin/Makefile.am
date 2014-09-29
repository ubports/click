plugindir = @pkpluginlibdir@/packagekit-plugins

plugin_LTLIBRARIES = libpk_plugin_click.la

libpk_plugin_click_la_SOURCES = pk-plugin-click.c

libpk_plugin_click_la_CPPFLAGS = -I$(top_builddir)/lib/click

libpk_plugin_click_la_CFLAGS = \
	@PKPLUGIN_CFLAGS@ \
	$(COVERAGE_CFLAGS)

libpk_plugin_click_la_LIBADD = \
	$(top_builddir)/lib/click/libclick-0.4.la \
	@PKPLUGIN_LIBS@

libpk_plugin_click_la_LDFLAGS = \
	$(COVERAGE_LDFLAGS) \
	-avoid-version

polkit_policydir = $(datadir)/polkit-1/actions

dist_polkit_policy_DATA = com.ubuntu.click.policy

@INTLTOOL_POLICY_RULE@

EXTRA_DIST = com.ubuntu.click.policy.in
DISTCLEANFILES = com.ubuntu.click.policy

polkit_localauthoritydir = $(localstatedir)/lib/polkit-1/localauthority/10-vendor.d

dist_polkit_localauthority_DATA = com.ubuntu.click.pkla
