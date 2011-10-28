# This source file is part of mc3p, the Minecraft Protocol Parsing Proxy.
#
# Copyright (C) 2011 Matthew J. McGill

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License v2 as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


from sys import version_info
from setuptools import setup, find_packages

basename = "mc3p"
version = "0.2pre"
pyversion = "%s.%s" % (version_info.major, version_info.minor)

setup(
    name = basename,
    version = version,
    packages = find_packages(),
    zip_safe = False,
    test_suite = 'test_plugins',
    author = "Matt McGill",
    author_email = "matt.mcgill@gmail.com",
    description = "Pluggable Minecraft proxy",
    keywords = "minecraft proxy",
    url = "http://mattmcgill.com/mc3p/%s-%s-%s.egg" % (basename, version, pyversion)
)


