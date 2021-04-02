import ast
import os
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
version_file = os.path.join(PROJECT_ROOT, 'f2format.py')

with open(version_file, 'r', encoding='utf-8') as f:
    code = f.read()

m = re.findall(r'(?am)^__version__(?:\s*)=(?:\s*)(.*?)$', code)
if not m:
    raise ValueError('cannot find version in source code')
if len(m) > 1:
    raise ValueError('multiple versions found in source code')
version = ast.literal_eval(m[0])
print(version)
