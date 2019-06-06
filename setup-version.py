# -*- coding: utf-8 -*-

import os
import re
import time

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

context = list()
with open(os.path.join(os.path.dirname(__file__), 'docker', 'Dockerfile')) as file:
    for line in file:
        match = re.match(r"LABEL version (.*)", line)
        if match is None:
            context.append(line)
        else:
            context.append(f'LABEL version {__version__}\n')

with open(os.path.join(os.path.dirname(__file__), 'docker', 'Dockerfile'), 'w') as file:
    file.writelines(context)

context = list()
with open(os.path.join(os.path.dirname(__file__), 'docs', 'f2format.rst')) as file:
    for line in file:
        match = re.match(r":Version: (.*)", line)
        if match is None:
            match = re.match(r":Date: (.*)", line)
            if match is None:
                context.append(line)
            else:
                context.append(f":Date: {time.strftime('%B %d, %Y')}\n")
        else:
            context.append(f':Version: v{__version__}\n')

with open(os.path.join(os.path.dirname(__file__), 'docs', 'f2format.rst'), 'w') as file:
    file.writelines(context)
