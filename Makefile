.PHONY: default pypi clean test flake

default: flake test

pypi:
	python setup.py sdist
	twine upload dist/*.tar.gz

clean:
	find . -name '*.py[co]' -delete
	find . -name '__pycache__' -delete
	rm -rf build/ dist/ *.egg *.egg-info/

test:
	SUBPROCESS_COVERAGE=1 POG_PASSPHRASE='hunter2' coverage run -m unittest
	coverage combine --append /tmp
	coverage report

flake:
	flake8
