# -*- coding: utf-8 -*-

import contextlib
import glob
import os
import shutil
import subprocess
import sys


def ispy(file):
    return (os.path.isfile(file) and (os.path.splitext(file)[1] == '.py'))


FLAG = True
for file in filter(ispy, os.listdir('.')):
    if file == __file__:
        continue
    subprocess.run([sys.executable, '../f2format.py', file])

    stem, ext = os.path.splitext(file)
    name = glob.glob('archive/%s*' % stem)[0]

    new = subprocess.run([sys.executable, file], stdout=subprocess.PIPE)
    old = subprocess.run([sys.executable, name], stdout=subprocess.PIPE)

    try:
        assert new.stdout == old.stdout
    except AssertionError:
        FLAG = False
        input(f'Test failed on {file!r}! Enter to continue...')

if FLAG:
    input('All tests passed, now restore backups...')
else:
    print('Tests failed, now restore backups...')
for file in os.listdir('.'):
    stem, ext = os.path.splitext(file)
    if ext == '.pyw' and os.path.exists('%s.py' % stem):
        shutil.copy(file, '%s.py' % stem)
shutil.rmtree('archive')
