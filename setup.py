# -*- coding: utf-8 -*-


import setuptools


# README
with open('./README.md', 'r') as file:
    long_desc = file.read()


# version string
__version__ = '0.1.0'


# set-up script for pip distribution
setuptools.setup(
    name = 'f2format',
    version = __version__,
    author = 'Jarry Shaw',
    author_email = 'jarryshaw@icloud.com',
    url = 'https://github.com/JarryShaw/f2format',
    license = 'MIT License',
    keywords = 'fstring format conversion',
    description = 'Convert f-string to str.format for Python 3 compatibility.',
    long_description = long_desc,
    long_description_content_type='text/markdown',
    python_requires = '>=3.6',
    install_requires = ['setuptools'],
    py_modules = ['f2format'],
    entry_points = {
        'console_scripts': [
            'f2format = f2format:main',
        ]
    },
    package_data = {
        '': [
            'LICENSE',
            'README.md',
            'CHANGELOG',
        ],
    },
    classifiers = [
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Environment :: MacOS X',
        'Environment :: Win32 (MS Windows)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development',
        'Topic :: Utilities',
    ]
)
