#!/usr/bin/env bash

# print a trace of simple commands
set -x

# update version string
python3 setup-version.py

# update Python stdlib files
rm -f src/token.py src/tokenize.py
token=$( python3 -c "print(__import__('token').__spec__.origin)" )
tokenize=$( python3 -c "print(__import__('tokenize').__spec__.origin)" )
cp -f ${token} ${tokenize} src/

# prepare for PyPI distribution
rm -rf build 2> /dev/null
mkdir eggs \
      sdist \
      wheels 2> /dev/null
mv -f dist/*.egg eggs/ 2> /dev/null
mv -f dist/*.whl wheels/ 2> /dev/null
mv -f dist/*.tar.gz sdist/ 2> /dev/null
rm -rf dist 2> /dev/null

# fetch platform spec
platform=$( python3 -c "import distutils.util; print(distutils.util.get_platform().replace('-', '_').replace('.', '_'))" )

# make distribution
python3.7 setup.py sdist bdist_egg bdist_wheel --plat-name="${platform}" --python-tag='cp37'
python3.6 setup.py bdist_egg bdist_wheel --plat-name="${platform}" --python-tag='cp36'
python3.5 setup.py bdist_egg bdist_wheel --plat-name="${platform}" --python-tag='cp35'
python3.4 setup.py bdist_egg bdist_wheel --plat-name="${platform}" --python-tag='cp34'
pypy3 setup.py bdist_wheel --plat-name="${platform}" --python-tag='pp35'

# distribute to PyPI and TestPyPI
twine upload dist/* -r pypi --skip-existing
twine upload dist/* -r pypitest --skip-existing

# get version string
version=$( cat f2format/__main__.py | grep "^__version__" | sed "s/__version__ = '\(.*\)'/\1/" )

# upload to GitHub
git pull
git tag "v${version}"
git add .
if [[ -z "$1" ]] ; then
    git commit -a -S
else
    git commit -a -S -m "$1"
fi
git push
ret="$?"
if [[ $ret -ne "0" ]] ; then
    exit $ret
fi

# file new release
go run github.com/aktau/github-release release \
    --user JarryShaw \
    --repo f2format \
    --tag "v${version}" \
    --name "f2format v${version}" \
    --description "$1"
ret="$?"
if [[ $ret -ne "0" ]] ; then
    exit $ret
fi

# update Homebrew Formulae
pipenv run python3 setup-formula.py
cd Tap
git pull && \
git add . && \
if [[ -z "$1" ]] ; then
    git commit -a -S
else
    git commit -a -S -m "$1"
fi && \
git push
ret="$?"
if [[ $ret -ne "0" ]] ; then
    exit $ret
fi

# update maintenance information
cd ..
maintainer changelog && \
maintainer contributor && \
maintainer contributing
ret="$?"
if [[ $ret -ne "0" ]] ; then
    exit $ret
fi

# aftermath
git pull && \
git add . && \
git commit -a -S -m "Regular update after distribution" && \
git push
