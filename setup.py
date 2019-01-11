# -*- coding: utf-8 -*-

import os
import re

try:
    from setuptools import Extension, setup
except ImportError:
    from distutils.core import Extension, setup

# README
with open('./README.md', encoding='utf-8') as file:
    long_desc = file.read()

# version string
__version__ = '0.4.2.dev1'

# Python 3.6
_ast36 = Extension(
    name='_ast36',
    sources=[
        'f2format/py36/ast/Parser/acceler.c',
        'f2format/py36/ast/Parser/bitset.c',
        'f2format/py36/ast/Parser/grammar.c',
        'f2format/py36/ast/Parser/grammar1.c',
        'f2format/py36/ast/Parser/node.c',
        'f2format/py36/ast/Parser/parser.c',
        'f2format/py36/ast/Parser/parsetok.c',
        'f2format/py36/ast/Parser/tokenizer.c',
        'f2format/py36/ast/Python/asdl.c',
        'f2format/py36/ast/Python/ast.c',
        'f2format/py36/ast/Python/graminit.c',
        'f2format/py36/ast/Python/Python-ast.c',
        'f2format/py36/ast/Custom/py36_ast.c',
    ],
    include_dirs=['f2format/py36/ast/Include'],
    depends=[
        'f2format/py36/ast/Include/asdl.h',
        'f2format/py36/ast/Include/ast.h',
        'f2format/py36/ast/Include/bitset.h',
        'f2format/py36/ast/Include/compile.h',
        'f2format/py36/ast/Include/errcode.h',
        'f2format/py36/ast/Include/graminit.h',
        'f2format/py36/ast/Include/grammar.h',
        'f2format/py36/ast/Include/node.h',
        'f2format/py36/ast/Include/parsetok.h',
        'f2format/py36/ast/Include/Python-ast.h',
        'f2format/py36/ast/Include/token.h',
        'f2format/py36/ast/Parser/parser.h',
        'f2format/py36/ast/Parser/tokenizer.h',
    ]
)

# Python 3.7
_ast37 = Extension(
    name='_ast37',
    sources=[
        'f2format/py37/ast/Parser/acceler.c',
        'f2format/py37/ast/Parser/bitset.c',
        'f2format/py37/ast/Parser/grammar.c',
        'f2format/py37/ast/Parser/grammar1.c',
        'f2format/py37/ast/Parser/node.c',
        'f2format/py37/ast/Parser/parser.c',
        'f2format/py37/ast/Parser/parsetok.c',
        'f2format/py37/ast/Parser/tokenizer.c',
        'f2format/py37/ast/Python/asdl.c',
        'f2format/py37/ast/Python/ast.c',
        'f2format/py37/ast/Python/graminit.c',
        'f2format/py37/ast/Python/Python-ast.c',
        'f2format/py37/ast/Custom/py37_ast.c',
    ],
    include_dirs=['f2format/py37/ast/Include'],
    depends=[
        'f2format/py37/ast/Include/asdl.h',
        'f2format/py37/ast/Include/ast.h',
        'f2format/py37/ast/Include/bitset.h',
        'f2format/py37/ast/Include/compile.h',
        'f2format/py37/ast/Include/errcode.h',
        'f2format/py37/ast/Include/graminit.h',
        'f2format/py37/ast/Include/grammar.h',
        'f2format/py37/ast/Include/node.h',
        'f2format/py37/ast/Include/parsetok.h',
        'f2format/py37/ast/Include/Python-ast.h',
        'f2format/py37/ast/Include/token.h',
        'f2format/py37/ast/Parser/parser.h',
        'f2format/py37/ast/Parser/tokenizer.h',
    ]
)

# set-up script for pip distribution
setup(
    name='f2format',
    version=__version__,
    author='Jarry Shaw',
    author_email='jarryshaw@icloud.com',
    url='https://github.com/JarryShaw/f2format',
    license='Apache Software License',
    keywords='fstring format conversion',
    description='Back-port compiler for Python 3.6 f-string literals.',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    python_requires='>=3.3',
    # include_package_data=True,
    zip_safe=True,
    install_requires=['typed_ast>=1.1.0'],
    extras_require={
        # ':python_version < "3.6"': ['typed_ast>=1.1.0'],
        ':python_version < "3.5"': ['pathlib2>=2.3.2'],
    },
    py_modules=['f2format'],
    packages=[
        'f2format',
        'f2format.py36',
        'f2format.py37',
    ],
    ext_modules=[
        _ast36,
        _ast37,
    ],
    entry_points={
        'console_scripts': [
            'f2format = f2format.__main__:main',
        ]
    },
    package_data={
        '': [
            'LICENSE',
            'README.md',
            'CHANGELOG.md',
        ],
    },
    classifiers=[
        'Development Status :: 6 - Mature',
        'Environment :: Console',
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development',
        'Topic :: Utilities',
    ]
)
