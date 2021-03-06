VIRTUALENV = virtualenv
PYTHON = bin/python
PIP = bin/pip
PIP_CACHE = /tmp/pip-cache.${USER}
BUILD_TMP = /tmp/syncstorage-build.${USER}
PYPI = https://pypi.python.org/simple
INSTALL = $(PIP) install -U -i $(PYPI)
FLAKE8 ?= ./bin/flake8
NOSETESTS ?= ./bin/nosetests

.PHONY: all build test

all:	build

build:
	$(VIRTUALENV) --no-site-packages --distribute .
	$(INSTALL) Distribute
	$(INSTALL) pip
	$(INSTALL) nose
	$(INSTALL) flake8
	$(INSTALL) -r requirements.txt
	$(PYTHON) ./setup.py develop

test:
	# Check that flake8 passes before bothering to run anything.
	# This can really cut down time wasted by typos etc.
	$(FLAKE8) shavar
	# Run the actual testcases.
	$(NOSETESTS) -s ./shavar/tests
