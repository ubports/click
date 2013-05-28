#! /usr/bin/perl
# debhelper sequence file for click-package

use warnings;
use strict;
use Debian::Debhelper::Dh_Lib;

insert_after("dh_install", "dh_clickpackage");

1;
