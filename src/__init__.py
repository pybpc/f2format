# -*- coding: utf-8 -*-

import os

import tbtrim

from f2format.core import *

__all__ = ['f2format', 'convert', 'ConvertError']


def predicate(filename):
    if os.path.basename(filename) == 'f2format':
        return True
    return (ROOT in os.path.realpath(filename))


tbtrim.set_trim_rule(predicate, strict=True, target=ConvertError)
