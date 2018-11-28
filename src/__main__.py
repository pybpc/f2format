# -*- coding: utf-8 -*-

import os
import shutil
import sys
import uuid

from f2format.core import f2format

# multiprocessing may not be supported
try:        # try first
    import multiprocessing
except ImportError:
    multiprocessing = None
else:       # CPU number if multiprocessing supported
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:
        CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')
    elif 'sched_getaffinity' in os.__all__:
        CPU_CNT = len(os.sched_getaffinity(0))  # pylint: disable=E1101
    else:
        CPU_CNT = os.cpu_count() or 1
finally:    # alias and aftermath
    mp = multiprocessing
    del multiprocessing

# backport compatibility
try:
    import pathlib2 as pathlib
except ImportError:
    import pathlib

# macros
ARCHIVE = 'archive'
HELPMSG = '''\
f2format 0.3.0
usage: f2format [-h] [-n] <python source files and folders..>

Convert f-string to str.format for Python 3 compatibility.

options:
    -h      show this help message and exit
    -n      do not archive original files
'''


def main():
    """Entry point for f2format."""
    def find(root):
        """Recursively find all files under root."""
        flst = list()
        temp = os.listdir(root)
        for file in temp:
            path = os.path.join(root, file)
            if os.path.isdir(path):
                flst.extend(find(path))
            elif os.path.isfile(path):
                flst.append(path)
            elif os.path.islink(path):  # exclude symbolic links
                continue
        yield from flst

    def rename(path):
        stem, ext = os.path.splitext(path)
        name = '%s-%s%s' % (stem, uuid.uuid4(), ext)
        return os.path.join(ARCHIVE, name)

    # help command
    if '-h' in sys.argv[1:]:
        print(HELPMSG)
        return

    # do not make archive
    archive = True
    if '-n' in sys.argv[1:]:
        archive = False

    # make archive directory
    if archive:
        pathlib.Path(ARCHIVE).mkdir(parents=True, exist_ok=True)

    # fetch file list
    filelist = list()
    for path in sys.argv[1:]:
        if os.path.isfile(path):
            if archive:
                dest = rename(path)
                pathlib.Path(dest).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(path, dest)
            filelist.append(path)
        if os.path.isdir(path):
            if archive:
                shutil.copytree(path, rename(path))
            filelist.extend(find(path))

    # check if file is Python source code
    def ispy(file): return (os.path.isfile(file) and (os.path.splitext(file)[1] in ('.py', '.pyw')))
    filelist = set(filter(ispy, filelist))

    # if no file supplied
    if len(filelist) == 0:
        print(HELPMSG)
        return

    # process files
    if mp is None:
        [f2format(filename) for filename in filelist]
    else:
        mp.Pool(processes=CPU_CNT).map(f2format, filelist)


if __name__ == '__main__':
    sys.exit(main())
