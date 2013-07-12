perllibdir = $(perl_vendorlib)/Debian/Debhelper/Sequence
debhelperdir = $(datadir)/debhelper/autoscripts

bin_SCRIPTS = dh_click
man1_MANS = dh_click.1
dist_perllib_DATA = click.pm
dist_debhelper_DATA = postinst-click prerm-click
CLEANFILES = $(man1_MANS)

%.1: %
	pod2man -c Debhelper -r $(PACKAGE_VERSION) $< $@
