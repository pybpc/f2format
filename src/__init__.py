# -*- coding: utf-8 -*-

import os

import tbtrim

from f2format.core import *

__all__ = ['f2format', 'convert']

ROOT = os.path.dirname(os.path.realpath(__file__))


def predicate(filename):  # pragma: no cover
    if os.path.basename(filename) == 'f2format':
        return True
    return (ROOT in os.path.realpath(filename))


tbtrim.set_trim_rule(predicate, strict=True, target=ConvertError)
