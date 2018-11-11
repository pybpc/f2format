# -*- coding: utf-8 -*-

import glob
import os
import shutil
import subprocess
import sys


def ispy(file):
    return (os.path.isfile(file) and (os.path.splitext(file)[1] == '.py'))


for file in filter(ispy, os.listdir('.')):
    if file == __file__:
        continue
    subprocess.run([sys.executable, '../f2format.py', file])

    stem, ext = os.path.splitext(file)
    name = glob.glob('archive/%s*' % stem)[0]

    new = subprocess.run([sys.executable, file], stdout=subprocess.PIPE)
    old = subprocess.run([sys.executable, name], stdout=subprocess.PIPE)

    assert new.stdout == old.stdout

print('All tests passed, now restore backups...')
for file in os.listdir('.'):
    stem, ext = os.path.splitext(file)
    if ext == '.pyw' and os.path.exists('%s.py' % stem):
        shutil.copy(file, '%s.py' % stem)
shutil.rmtree('archive')
