#!/usr/bin/env bash

set -x

# change CWD
cd /f2format

# set alias
alias pypy3="PYTHONPATH=/usr/local/lib/pypy3.5/dist-packages pypy3"

# make distribution
python3.7 setup.py sdist bdist_egg bdist_wheel --plat-name="manylinux1_x86_64" --python-tag='cp37' && \
python3.6 setup.py bdist_egg bdist_wheel --plat-name="manylinux1_x86_64" --python-tag='cp36' && \
python3.5 setup.py bdist_egg bdist_wheel --plat-name="manylinux1_x86_64" --python-tag='cp35' && \
python3.4 setup.py bdist_egg bdist_wheel --plat-name="manylinux1_x86_64" --python-tag='cp34' && \
pypy3 setup.py bdist_wheel --plat-name="manylinux1_x86_64" --python-tag='pp35'
exit $?
