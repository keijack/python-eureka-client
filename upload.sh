#!/bin/bash

rm dist/*

python3 -m pip install --upgrade build twine pkginfo

python3 -m build --sdist --wheel .

python3 -m twine check dist/*

python3 -m twine upload dist/*