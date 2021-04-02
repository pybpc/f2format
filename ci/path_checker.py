import importlib
import os
import re
import sys

module_name = 'f2format'

if not os.path.isfile('setup.py'):
    sys.exit('Please execute this script in the project root directory.')

sys.path.insert(0, '.')

path = importlib.import_module(module_name).__file__
print('Module {} is located at: {}'.format(module_name, path))

if len(sys.argv) > 1 and sys.argv[1] == 'strict' and not re.search(r'\b(?:site|dist)-packages\b', path):
    sys.exit('Error: module {} is not an installed version'.format(module_name))
