.PHONY: clean docker release pipenv pypi setup dist

export PIPENV_VENV_IN_PROJECT=1

SHELL := /usr/local/bin/bash
DIR   ?= .

# fetch platform spec
platform = $(shell python3 -c "import distutils.util; print(distutils.util.get_platform().replace('-', '_').replace('.', '_'))")
# get version string
version  = $(shell cat f2format/__main__.py | grep "^__version__" | sed "s/__version__ = '\(.*\)'/\1/")
# builtins.token
token    = $(shell python3 -c "print(__import__('token').__spec__.origin)")
# builtins.tokenize
tokenize = $(shell python3 -c "print(__import__('tokenize').__spec__.origin)")
# commit message
message  ?= ""

clean: clean-pyc clean-misc clean-pypi
docker: setup-version docker-build
release: release-master release-devel
pipenv: update-pipenv
pypi: dist-pypi dist-upload
setup: setup-version setup-formula

# setup pipenv
setup-pipenv: clean-pipenv
	pipenv install --dev

# update version string
setup-version:
	python3 setup-version.py

# update Homebrew Formulae
setup-formula: pipenv
	pipenv run python3 setup-formula.py

# update Python stdlib files
setup-stdlib:
	rm -f src/token.py src/tokenize.py
	cp -f $(token) $(tokenize) src/

# remove *.pyc
clean-pyc:
	find $(DIR) -iname __pycache__ | xargs rm -rf
	find $(DIR) -iname '*.pyc' | xargs rm -f

# remove devel files
clean-misc: clean-pyc
	find $(DIR) -iname .DS_Store | xargs rm -f

# remove pipenv
clean-pipenv:
	pipenv --rm

# prepare for PyPI distribution
.ONESHELL:
clean-pypi:
	set -ex
	cd $(DIR)
	mkdir -p sdist eggs wheels
	find dist -iname '*.egg' -exec mv {} eggs \;
	find dist -iname '*.whl' -exec mv {} wheels \;
	find dist -iname '*.tar.gz' -exec mv {} sdist \;
	rm -rf build dist *.egg-info

# update pipenv
update-pipenv:
	pipenv update
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
	cp -rf src release/f2format
	cp setup.py \
	   setup.cfg \
	   README.md \
	   Dockerfile \
	   MANIFEST.in \
	   .dockerignore release
	DIR=release $(MAKE) clean-pyc

docker-build: docker-prep
	docker build --tag f2format:$(version) --tag f2format:latest release

# make PyPI distribution
dist-pypi: clean-pypi dist-macos dist-linux

.ONESHELL:
dist-macos:
	set -ex
	cd $(DIR)
	python3.7 setup.py sdist bdist_egg bdist_wheel --plat-name="$(platform)" --python-tag='cp37'
	python3.6 setup.py bdist_egg bdist_wheel --plat-name="$(platform)" --python-tag='cp36'
	python3.5 setup.py bdist_egg bdist_wheel --plat-name="$(platform)" --python-tag='cp35'
	python3.4 setup.py bdist_egg bdist_wheel --plat-name="$(platform)" --python-tag='cp34'
	pypy3 setup.py bdist_wheel --plat-name="$(platform)" --python-tag='pp35'

.ONESHELL:
dist-linux:
	set -ex
	cd $(DIR)/docker
	sed "s/LABEL version.*/LABEL version $(shell date +%Y.%m.%d)/" Dockerfile > Dockerfile.tmp
	mv Dockerfile.tmp Dockerfile
	docker-compose up --build

# upload PyPI distribution
.ONESHELL:
dist-upload:
	set -ex
	cd $(DIR)
	twine check dist/*
	twine upload dist/* -r pypi --skip-existing
	twine upload dist/* -r pypitest --skip-existing

# add tag
.ONESHELL:
git-tag:
	set -ex
	cd $(DIR)
	git tag "v$(version)"

# upload to GitHub
.ONESHELL:
git-upload:
	set -ex
	cd $(DIR)
	git pull
	git add .
	if [[ -z "$(message)" ]] ; then \
		git commit -a -S ; \
	else \
		git commit -a -S -m "$(message)" ; \
	fi
	git push

# upload after distro
git-aftermath:
	git pull
	git add .
	git commit -a -S -m "Regular update after distribution"
	git push

# file new release on master
release-master:
	go run github.com/aktau/github-release release \
		--user JarryShaw \
		--repo f2format \
		--tag "v$(version)" \
		--name "f2format v$(version)" \
		--description "$(message)"

# file new release on devel
release-devel:
	go run github.com/aktau/github-release release \
		--user JarryShaw \
		--repo f2format \
		--tag "v$(version).devel" \
		--name "f2format v$(version).devel" \
		--description "$(message)" \
		--target "devel" \
		--pre-release

# run distribution process
dist:
	$(MAKE) message=$(message) \
		setup-version setup-stdlib \
		clean pypi git-tag git-upload \
		release setup-formula
	$(MAKE) message=$(message) DIR=Tap \
		git-upload
	$(MAKE) message=$(message) \
		update-maintainer git-aftermath
