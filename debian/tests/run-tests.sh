#!/bin/sh

set -e

TEST_INTEGRATION=1 python3 -m unittest discover tests.integration
