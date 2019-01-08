# -*- coding: utf-8 -*-

import os
import sys

from f2format.core import *

__all__ = ['f2format', 'convert']

# library version
version = sys.version_info[:2]
if version == (3, 6):
    os.environ['F2FORMAT_PYTHONVERSION'] = 'py36'
else:
    os.environ['F2FORMAT_PYTHONVERSION'] = 'py37'
