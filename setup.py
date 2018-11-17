# -*- coding: utf-8 -*-

import os
import re

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

# README
with open('./README.md', 'r') as file:
    long_desc = file.read()

# version string
with open(os.path.join(os.path.dirname(__file__), 'f2format.py'), 'r') as file:
    for line in file:
        match = re.match(r'f2format (.*)', line)
        if match is None:
            continue
        __version__ = match.groups()[0]
        break

# set-up script for pip distribution
setup(
    name='f2format',
    version=__version__,
    author='Jarry Shaw',
    author_email='jarryshaw@icloud.com',
    url='https://github.com/JarryShaw/f2format',
    license='MIT License',
    keywords='fstring format conversion',
    description='Back-port compiler for Python 3.6 f-string literals.',
    long_description=long_desc,
    long_description_content_type='text/markdown',
    python_requires='>=3.3',
    extras_require={
        ':python_version < "3.6"': ['typed_ast>=1.1.0'],
        ':python_version < "3.5"': ['pathlib2>=2.3.2'],
    },
    py_modules=['f2format'],
    entry_points={
        'console_scripts': [
            'f2format = f2format:main',
        ]
    },
    package_data={
        '': [
            'LICENSE',
            'README.md',
            'CHANGELOG',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
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
