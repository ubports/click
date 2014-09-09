#!/bin/sh

set -e

# some files like config.py are generated from config.py.in
./autogen.sh
./configure

TEST_INTEGRATION=1 python3 -m unittest discover -vv click.tests.integration
