#! /bin/sh
set -e
intltoolize --copy --force --automake
autoreconf -fi
# We want to keep po/click.pot in the source package.
sed -i '/rm .*\$(GETTEXT_PACKAGE)\.pot/s/ \$(GETTEXT_PACKAGE)\.pot//' \
	po/Makefile.in.in
