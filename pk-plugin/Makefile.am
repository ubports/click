plugindir = @pkpluginlibdir@/packagekit-plugins

plugin_LTLIBRARIES = libpk_plugin_click.la

libpk_plugin_click_la_SOURCES = pk-plugin-click.c

libpk_plugin_click_la_CFLAGS = @PKPLUGIN_CFLAGS@

libpk_plugin_click_la_LIBADD = @PKPLUGIN_LIBS@

libpk_plugin_click_la_LDFLAGS = -avoid-version

polkit_policydir = $(datadir)/polkit-1/actions

dist_polkit_policy_DATA = com.ubuntu.click.policy

@INTLTOOL_POLICY_RULE@

EXTRA_DIST = com.ubuntu.click.policy.in
DISTCLEANFILES = com.ubuntu.click.policy
