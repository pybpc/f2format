import os
import subprocess  # nosec
import sys
from typing import List, Sequence

import colorlabels as cl
from typing_extensions import TypedDict

if not os.path.isfile('setup.py'):
    sys.exit('Please execute this script in the project root directory.')

Linter = TypedDict('Linter', {'name': str, 'command': Sequence[str]})

linters = [
    {
        'name': 'Flake8',
        'command': ['flake8'],
    },
    {
        'name': 'Pylint',
        'command': [sys.executable, os.path.join('ci', 'run_pylint.py')],
    },
    {
        'name': 'Mypy',
        'command': ['mypy', '.'],
    },
    {
        'name': 'Bandit',
        'command': ['bandit', '-c', 'bandit.yml', '-r', '.'],
    },
    {
        'name': 'Vermin',
        'command': ['vermin', '.'],
    },
]  # type: List[Linter]


def run_linter(linter: Linter) -> bool:
    linter_name = linter['name']
    cl.progress('Running linter {}'.format(linter_name))
    result = subprocess.call(linter['command'])  # nosec
    if result == 0:
        cl.success('Linter {} success'.format(linter_name))
        return True
    cl.error('Linter {} failed'.format(linter_name))
    return False


# Avoid short-circuiting to show all linter output at the same time.
all_results = [run_linter(linter) for linter in linters]  # type: List[bool]

if all(all_results):
    cl.success('All linters success')
else:
    cl.error('Some linters failed, check output for more information')
    sys.exit(1)
