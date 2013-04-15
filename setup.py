#! /usr/bin/env python3

import re

from setuptools import find_packages, setup


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


setup(
    name="click-package",
    version=version,
    description="Click package manager",
    author="Colin Watson",
    author_email="cjwatson@ubuntu.com",
    license="GNU GPL",
    packages=find_packages(),
    scripts=[
        'bin/click-build',
        'bin/click-install',
    ],
    test_suite="clickpackage.tests",
)
