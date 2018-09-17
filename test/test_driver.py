# -*- coding: utf-8 -*-


import glob
import os
import shutil
import subprocess
import sys


ispy = lambda file: (os.path.isfile(file) and (os.path.splitext(file)[1] in ('.py', '.pyw')))
for file in filter(ispy, os.listdir('.')):
    if file == __file__:   continue
    subprocess.run([sys.executable, '../f2format.py', file])

    stem, ext = os.path.splitext(file)
    name = glob.glob('archive/%s*' % stem)[0]

    new = subprocess.run([sys.executable, file], stdout=subprocess.PIPE)
    old = subprocess.run([sys.executable, name], stdout=subprocess.PIPE)

    assert new.stdout == old.stdout

print('All tests passed, now restore backups...')
for file in filter(ispy, os.listdir('archive')):
    stem, ext = os.path.splitext(file)
    os.rename(os.path.join('archive', file), '%s%s' % (stem.rsplit('-', 1)[0], ext))
shutil.rmtree('archive')
