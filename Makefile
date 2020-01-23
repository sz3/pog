pypi:
	python setup.py sdist
	twine upload dist/*.tar.gz

clean:
	find . -name '*.py[co]' -delete
	find . -name '__pycache__' -delete
	rm -rf build/ dist/ *.egg *.egg-info/
