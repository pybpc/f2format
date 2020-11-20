# -*- coding: utf-8 -*-

import os
import shutil
import subprocess  # nosec: B404
import sys

try:
    import f2format  # pylint: disable=unused-import
except ImportError:
    sys.exit('Wrong interpreter...')

# change cwd to current directory of this file
os.chdir(os.path.dirname(os.path.realpath(__file__)))


def ispy(file):  # pylint: disable=redefined-outer-name
    return os.path.isfile(file) and (os.path.splitext(file)[1] == '.py')


FLAG = True
for file in sorted(filter(ispy, os.listdir('.'))):
    if file == os.path.split(__file__)[1]:
        continue

    # skip unparenthesized test on Python < 3.6 due to parso requirement
    if file == 'unparenthesized.py' and sys.version_info < (3, 6):
        continue

    subprocess.run([sys.executable, '-m', 'f2format', file])  # nosec: B603; pylint: disable=subprocess-run-check

    stem, ext = os.path.splitext(file)
    name = '%s.pyw' % stem

    new = subprocess.run([sys.executable, file], stdout=subprocess.PIPE)  # nosec: B603; pylint: disable=subprocess-run-check
    old = subprocess.run([sys.executable, name], stdout=subprocess.PIPE)  # nosec: B603; pylint: disable=subprocess-run-check

    try:
        assert new.stdout == old.stdout  # nosec: B101
    except AssertionError:
        FLAG = False
        print(f'Test failed on {file!r}!')
        print(f'EXPECT:\n{old.stdout.decode()}')
        print(f'GOT:\n{new.stdout.decode()}')
        input('Enter to continue...')  # nosec: B322

if FLAG:
    input('All tests passed, now restore backups...')  # nosec: B322
else:
    print('Tests failed, now restore backups...')
for file in os.listdir('.'):
    stem, ext = os.path.splitext(file)
    if ext == '.pyw' and os.path.exists('%s.py' % stem):
        shutil.copy(file, '%s.py' % stem)
shutil.rmtree('archive')
