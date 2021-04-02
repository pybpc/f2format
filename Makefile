.PHONY: docs

export PIPENV_VERBOSITY=-1

update: pipenv-update

docs:
	pipenv run $(MAKE) -C docs html

coverage:
	pipenv run coverage run -m pytest --color=yes
	pipenv run coverage html
	open htmlcov/index.html
	echo "Press ENTER to continue..."
	read
	rm -rf htmlcov
	rm .coverage

test:
	pipenv run pytest --color=yes

pipenv-init:
	pipenv install --dev

pipenv-update:
	pipenv run pip install -U \
	    pip \
	    setuptools \
	    wheel
	while true; do \
	    pipenv update && break ; \
	done
	pipenv install --dev
	pipenv clean

pipenv-deinit:
	pipenv --rm

manpage:
	pipenv run rst2man.py share/f2format.rst > share/f2format.1
