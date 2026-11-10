"""Avoid embedding workstation paths in published firmware."""
from pathlib import Path
Import('env')
env.Append(BUILD_FLAGS=['-ffile-prefix-map=' + str(Path.home()) + '=/build'])
