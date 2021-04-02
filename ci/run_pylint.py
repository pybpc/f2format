import itertools
import os
import pathlib
import subprocess  # nosec
import sys
from typing import List

if not os.path.isfile('setup.py'):
    sys.exit('Please execute this script in the project root directory.')

# pylint: disable=line-too-long
pylint_args = [
    '--load-plugins=pylint.extensions.check_elif,pylint.extensions.docstyle,pylint.extensions.emptystring,pylint.extensions.overlapping_exceptions',
    '--disable=all',
    '--enable=F,E,W,R,basic,classes,format,imports,refactoring,else_if_used,docstyle,compare-to-empty-string,overlapping-except',
    '--disable=blacklisted-name,invalid-name,missing-class-docstring,missing-function-docstring,missing-module-docstring,design,too-many-lines,eq-without-hash,old-division,no-absolute-import,input-builtin,too-many-nested-blocks',
    '--max-line-length=120',
    '--init-import=yes',
]  # type: List[str]
# pylint: enable=line-too-long

current_dir = pathlib.Path('.')
py_files = sorted(map(str, itertools.chain(
    current_dir.glob('./**/*.py'),
    current_dir.glob('./**/*.pyw'),
    current_dir.glob('./**/*.py3'),
    current_dir.glob('./**/*.pyi'),
)))

sys.exit(subprocess.call(['pylint'] + pylint_args + ['--'] + py_files))  # nosec
