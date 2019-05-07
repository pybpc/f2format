# -*- coding: utf-8 -*-

import contextlib
import glob
import os
import shutil
import subprocess
import sys

try:
    import f2format
except ImportError:
    sys.exit('Wrong interpreter...')

# change cwd to current directory of this file
os.chdir(os.path.dirname(os.path.realpath(__file__)))


def ispy(file):
    return (os.path.isfile(file) and (os.path.splitext(file)[1] == '.py'))


FLAG = True
for file in sorted(filter(ispy, os.listdir('.'))):
    if file == os.path.split(__file__)[1]:
        continue
    subprocess.run([sys.executable, '-m', 'f2format', file])

    stem, ext = os.path.splitext(file)
    name = glob.glob('archive/%s*' % stem)[0]

    new = subprocess.run([sys.executable, file], stdout=subprocess.PIPE)
    old = subprocess.run([sys.executable, name], stdout=subprocess.PIPE)

    try:
        assert new.stdout == old.stdout
    except AssertionError:
        FLAG = False
        print(f'Test failed on {file!r}!')
        print(f'EXPECT:\n{old.stdout.decode()}')
        print(f'GOT:\n{new.stdout.decode()}')
        input('Enter to continue...')

if FLAG:
    input('All tests passed, now restore backups...')
else:
    print('Tests failed, now restore backups...')
for file in os.listdir('.'):
    stem, ext = os.path.splitext(file)
    if ext == '.pyw' and os.path.exists('%s.py' % stem):
        shutil.copy(file, '%s.py' % stem)
shutil.rmtree('archive')
