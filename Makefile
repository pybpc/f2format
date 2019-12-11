.PHONY: clean docker release pipenv pypi setup dist test coverage

include .env

export PIPENV_VENV_IN_PROJECT
export CODECOV_TOKEN

SHELL := /usr/local/bin/bash

# fetch platform spec
platform = $(shell python3 -c "import distutils.util; print(distutils.util.get_platform().replace('-', '_').replace('.', '_'))")
# get version string
version  = $(shell cat f2format.py | grep "^__version__" | sed "s/__version__ = '\(.*\)'/\1/")
# pre-release flag
flag     = $(shell python3 -c "print(__import__('pkg_resources').parse_version('${version}').is_prerelease)")

clean: clean-pyc clean-misc clean-pypi
docker: setup-version docker-build
pipenv: update-pipenv
pypi: dist-pypi dist-upload
setup: setup-version setup-manpages
test: test-unittest test-interactive

test-unittest:
	pipenv run python share/test.py

test-interactive:
	pipenv run python test/test_driver.py

coverage:
	pipenv run coverage run share/test.py
	pipenv run coverage html
	open htmlcov/index.html
	read
	rm -rf htmlcov
	rm .coverage

# setup pipenv
setup-pipenv: clean-pipenv
	pipenv install --dev

# update version string
setup-version:
	[[ ${flag} -eq "False" ]] && python3 share/setup-version.py

# update Homebrew Formulae
setup-formula: pipenv
	pipenv run python3 share/setup-formula.py

# update manpages
setup-manpages:
	rm -f share/f2format.1
	pipenv run rst2man.py share/f2format.rst > share/f2format.1

# remove *.pyc
clean-pyc:
	find . -iname __pycache__ | xargs rm -rf
	find . -iname '*.pyc' | xargs rm -f

# remove devel files
clean-misc: clean-pyc
	find . -iname .DS_Store | xargs rm -f

# remove pipenv
clean-pipenv:
	pipenv --rm

# prepare for PyPI distribution
clean-pypi:
	mkdir -p dist sdist eggs wheels
	find dist -iname '*.egg' -exec mv {} eggs \;
	find dist -iname '*.whl' -exec mv {} wheels \;
	find dist -iname '*.tar.gz' -exec mv {} sdist \;
	rm -rf build dist *.egg-info

# update pipenv
update-pipenv:
	pipenv run pip install -U pip setuptools wheel
	while true; do \
            pipenv update && break ; \
        done
	pipenv install --dev
	pipenv clean

# update maintenance information
update-maintainer:
	go run github.com/gaocegege/maintainer changelog
	go run github.com/gaocegege/maintainer contributor
	go run github.com/gaocegege/maintainer contributing

docker-prep:
	rm -rf release
	mkdir -p release
	cp setup.py \
	   setup.cfg \
	   README.md \
	   MANIFEST.in \
	   docker/Dockerfile \
	   docker/.dockerignore \
	   f2format.py release
	DIR=release $(MAKE) clean-pyc

docker-build: docker-prep
	docker build --tag f2format:$(version) --tag f2format:latest release

# make PyPI distribution
dist-pypi: clean-pypi dist-pypi-setup

dist-pypi-setup:
	python3 setup.py sdist bdist_wheel

# upload PyPI distribution
dist-upload:
	twine check dist/* || true
	twine upload dist/* -r pypi --skip-existing
	twine upload dist/* -r pypitest --skip-existing

# upload to GitHub
git-upload:
	git pull
	git add .
	git commit -a -S
	git push

# upload after distro
git-aftermath: git-submodule
	git pull
	git add .
	git commit -a -S -m "Regular update after distribution"
	git push

# file new release
release:
	go run github.com/aktau/github-release release \
	    --user JarryShaw \
	    --repo f2format \
	    --tag "v$(version)" \
	    --name "f2format v$(version)" \
	    --description "$$(git log -1 --pretty=%B)"

# run distribution process
dist: dist_1st dist_2nd dist_3rd

dist_1st: test-unittest setup clean pypi git-upload release

.ONESHELL:
dist_2nd: setup-formula
	set -ae
	cd Tap
	git pull
	git add Formula/f2format.rb
	git commit -S -m "f2format: $(version)"
	git push

dist_3rd: update-maintainer git-aftermath
