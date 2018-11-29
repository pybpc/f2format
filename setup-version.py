# -*- coding: utf-8 -*-

import os
import re

with open('./f2format/__main__.py', 'r') as file:
    for line in file:
        match = re.match(r"^__version__ = '(.*)'", line)
        if match is None:
            continue
        __version__ = match.groups()[0]
        break

context = list()
with open(os.path.join(os.path.dirname(__file__), 'setup.py')) as file:
    for line in file:
        match = re.match(r"__version__ = '(.*)'", line)
        if match is None:
            context.append(line)
        else:
            context.append(f'__version__ = {__version__!r}\n')

with open(os.path.join(os.path.dirname(__file__), 'setup.py'), 'w') as file:
    file.writelines(context)
