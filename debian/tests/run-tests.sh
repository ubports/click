#!/bin/sh

set -e

# some files like config.py are generated from config.py.in
./autogen.sh
./configure --prefix=/usr \
        --sysconfdir=/etc \
        --with-systemdsystemunitdir=/lib/systemd/system \
        --with-systemduserunitdir=/usr/lib/systemd/user \
        --disable-packagekit

TEST_INTEGRATION=1 python3 -m unittest discover -vv click_package.tests.integration
