#! /usr/bin/env python3

import os
import re
import subprocess
import sys

from setuptools import Command, find_packages, setup
from distutils.command.build import build
from distutils.command.clean import clean


# We probably ought to use debian.changelog, but let's avoid that dependency
# for now.
changelog_heading = re.compile(r"\w[-+0-9a-z.]* \(([^\(\) \t]+)\)")

with open("debian/changelog") as changelog:
    line = changelog.readline()
    match = changelog_heading.match(line)
    if match is None:
        raise ValueError(
            "Failed to parse first line of debian/changelog: '%s'" % line)
    version = match.group(1)


class build_extra(build):
    def __init__(self, dist):
        build.__init__(self, dist)

        self.user_options.extend([('pod2man', None, 'use pod2man')])

    def initialize_options(self):
        build.initialize_options(self)
        self.pod2man = False

    def finalize_options(self):
        def has_pod2man(command):
            return self.pod2man == 'True'

        build.finalize_options(self)
        self.sub_commands.append(('build_pod2man', has_pod2man))


class build_pod2man(Command):
    description = "build POD manual pages"

    user_options = [('pod-files=', None, 'POD files to build')]

    def initialize_options(self):
        self.pod_files = []

    def finalize_options(self):
        pass

    def run(self):
        for pod_file in self.distribution.scripts:
            if not pod_file.startswith('debhelper/'):
                continue
            if os.path.exists('%s.1' % pod_file):
                continue
            self.spawn(['pod2man', '-c', 'Debhelper', '-r', version,
                        pod_file, '%s.1' % pod_file])


class clean_extra(clean):
    def run(self):
        clean.run(self)

        for path, dirs, files in os.walk('.'):
            for f in files:
                f = os.path.join(path, f)
                if f.startswith('./debhelper') and f.endswith('.1'):
                    self.spawn(['rm', f])


requirements = []
def require(package, pypi_name=None):
    try:
        __import__(package)
    except ImportError:
        requirements.append(package if pypi_name is None else pypi_name)


require('debian', 'python-debian')
if sys.version < "3.3":
    require('mock')
require('chardet')


perl_vendorlib = subprocess.Popen(
    ['perl', '-MConfig', '-e', 'print $Config{vendorlib}'],
    stdout=subprocess.PIPE, universal_newlines=True).communicate()[0]
if not perl_vendorlib:
    raise ValueError("Failed to get $Config{vendorlib} from perl")
perllibdir = '%s/Debian/Debhelper/Sequence' % perl_vendorlib


# Hack to avoid install_data breaking in ./run-tests.
if os.getuid() == 0:
    data_files = [
        (perllibdir, ['debhelper/click.pm']),
        ('/usr/share/debhelper/autoscripts', [
            'debhelper/postinst-click',
            'debhelper/prerm-click',
            ]),
        ('/usr/share/man/man1', [
            'debhelper/dh_click.1',
            ])]
else:
    data_files = []


setup(
    name="click",
    version=version,
    description="Click package manager",
    author="Colin Watson",
    author_email="cjwatson@ubuntu.com",
    license="GNU GPL",
    packages=find_packages(),
    scripts=[
        'bin/click',
        'debhelper/dh_click',
        ],
    data_files=data_files,
    cmdclass={
        'build': build_extra,
        'build_pod2man': build_pod2man,
        'clean': clean_extra,
        },
    install_requires=requirements,
    test_suite="click.tests",
    )
