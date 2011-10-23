
from sys import version_info
from setuptools import setup, find_packages

basename = "mc3p"
version = "0.1"
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


