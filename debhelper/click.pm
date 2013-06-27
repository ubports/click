#! /usr/bin/perl
# debhelper sequence file for click

use warnings;
use strict;
use Debian::Debhelper::Dh_Lib;

insert_after("dh_install", "dh_click");

1;
