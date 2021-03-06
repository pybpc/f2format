#!/usr/bin/env bash

# [NB]
# This is a demo script for those who is to integrate
# `f2format` in development and distribution circle.
#
# It assumes
# 	- all source files in `/src` directory
# 	- using GitHub for repository management
# 	- having release branch under `/release` directory
# 	- already installed `f2format` and `twine`
# 	- permission to these files and folders granted

# And it will
# 	- copy `setup.py` and `src` to `release` directory
# 	- run `f2format` for Python files under `release`
# 	- distribute to PyPI and TestPyPI using `twine`
# 	- upload to release branch on GitHub
# 	- upload original files to GitHub

# print trace of simple commands
set -x

# duplicate distribution files
cp -rf MANIFEST.in \
       setup.cfg \
       setup.py \
       src release/
cd release/

# perform f2format
f2format -n src
returncode="$?"
if [[ ${returncode} -ne "0" ]] ; then
    exit ${returncode}
fi

# prepare for PyPI distribution
mkdir -p eggs sdist wheels
rm -rf build
mv -f dist/*.egg eggs/
mv -f dist/*.whl wheels/
mv -f dist/*.tar.gz sdist/

# distribute to PyPI and TestPyPI
python setup.py sdist bdist_wheel && \
twine check dist/* && \
twine upload dist/* -r pypi --skip-existing && \
twine upload dist/* -r pypitest --skip-existing
returncode="$?"
if [[ ${returncode} -ne "0" ]] ; then
    exit ${returncode}
fi

# upload to GitHub
git pull && \
git add . && \
if [[ -z "$1" ]] ; then
    git commit -a
else
    git commit -a -m "$1"
fi && \
git push
returncode="$?"
if [[ ${returncode} -ne "0" ]] ; then
    exit ${returncode}
fi

# # [optional] archive original files
# for file in $( ls archive ) ; do
#     if [[ -d "archive/${file}" ]] ; then
#         tar -cvzf "archive/${file}.tar.gz" "archive/${file}"
#         rm -rf "archive/${file}"
#     fi
# done

# upload develop environment
cd ..
git pull && \
git add . && \
if [[ -z "$1" ]] ; then
    git commit -a
else
    git commit -a -m "$1"
fi && \
git push
