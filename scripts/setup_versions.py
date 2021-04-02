import os
import re
import subprocess  # nosec
import sys
import time

os.chdir(os.path.dirname(
    os.path.dirname(os.path.realpath(__file__))
))

version = subprocess.check_output([sys.executable,  # nosec
                                   os.path.join('scripts', 'find_version.py')],
                                  universal_newlines=True).strip()

context = []
with open(os.path.join('share', 'f2format.rst')) as file:
    for line in file:
        match = re.match(r":Version: (.*)", line)
        if match is None:
            match = re.match(r":Date: (.*)", line)
            if match is None:
                context.append(line)
            else:
                context.append(f":Date: {time.strftime('%B %d, %Y')}\n")
        else:
            context.append(f':Version: v{version}\n')

with open(os.path.join('share', 'f2format.rst'), 'w') as file:
    file.writelines(context)

context.clear()
with open(os.path.join('docs', 'source', 'conf.py')) as file:
    for line in file:
        match = re.match(r"release = (.*)", line)
        if match is None:
            context.append(line)
        else:
            context.append(f'release = {version!r}\n')

with open(os.path.join('docs', 'source', 'conf.py'), 'w') as file:
    file.writelines(context)
