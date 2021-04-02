# NB: f2format is currently under reconstruction. It is highly recommended to directly install from the git repo or the pre-release distributions.

---

# f2format

[![PyPI - Downloads](https://pepy.tech/badge/f2format)](https://pepy.tech/count/f2format)
[![PyPI - Version](https://img.shields.io/pypi/v/bpc-f2format.svg)](https://pypi.org/project/bpc-f2format)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bpc-f2format.svg)](https://pypi.org/project/bpc-f2format)

[![GitHub Actions - Status](https://github.com/pybpc/bpc-f2format/workflows/Build/badge.svg)](https://github.com/pybpc/bpc-f2format/actions?query=workflow%3ABuild)
[![Codecov - Coverage](https://codecov.io/gh/pybpc/bpc-f2format/branch/master/graph/badge.svg)](https://codecov.io/gh/pybpc/bpc-f2format)
[![Documentation Status](https://readthedocs.org/projects/bpc-f2format/badge/?version=latest)](https://bpc-f2format.readthedocs.io/en/latest/)

> Write *f-string* in Python 3.6 flavour, and let `f2format` worry about back-port issues :beer:

&emsp; Since [PEP 498](https://www.python.org/dev/peps/pep-0498/), Python introduced
*[f-string](https://docs.python.org/3/reference/lexical_analysis.html#formatted-string-literals)*
literals in version __3.6__. Though released ever since
[December 23, 2016](https://docs.python.org/3.6/whatsnew/changelog.html#python-3-6-0-final), Python
3.6 is still not widely used as expected. For those who are now used to *f-string*s, `f2format`
provides an intelligent, yet imperfect, solution of a **backport compiler** by converting
*f-string*s to `str.format` expressions, which guarantees you to always write *f-string*s in Python
3.6 flavour then compile for compatibility later.

&emsp; `f2format` is inspired and assisted by my good mate [@gousaiyang](https://github.com/gousaiyang).
It functions by tokenising and parsing Python code into multiple abstract syntax trees (AST),
through which it shall synthesise and extract expressions from *f-string* literals, and then
reassemble the original string using `str.format` method. Besides
**[conversion](https://docs.python.org/3/library/string.html#format-string-syntax)** and
**[format specification](https://docs.python.org/3/library/string.html#formatspec)**, `f2format`
also considered and resolved
**[string concatenation](https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation)**.
Also, it always tries to maintain the original layout of source code, and accuracy of syntax.

## Documentation

&emsp; See [documentation](https://bpc-f2format.readthedocs.io/en/latest/) for usage and more details.

## Contribution

&emsp; Contributions are very welcome, especially fixing bugs and providing test cases.
Note that code must remain valid and reasonable.

## See Also

- [`pybpc`](https://github.com/pybpc/bpc) (formerly known as `python-babel`)
- [`poseur`](https://github.com/pybpc/poseur)
- [`walrus`](https://github.com/pybpc/walrus)
- [`relaxedecor`](https://github.com/pybpc/relaxedecor)
- [`vermin`](https://github.com/netromdk/vermin)
