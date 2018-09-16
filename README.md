# f2format

&emsp; Since [PEP 498](https://www.python.org/dev/peps/pep-0498/), Python introduced *[f-string](https://docs.python.org/3/reference/lexical_analysis.html#formatted-string-literals)* literal in version __3.6__. Though released ever since [December 23, 2016](https://docs.python.org/3.6/whatsnew/changelog.html#python-3-6-0-final), Python 3.6 is still not widely used as expected. For those who are now used to *f-string*, `f2format` provides an intelligent, yet imperfect, solution of a **backport compiler** by converting *f-string*s to `str.format` literals.

&emsp; `f2format` is inspired and assisted by my mate [@gousaiyang](https://github.com/gousaiyang). It functions by tokenising and parsing Python code into multiple abstract syntax trees (AST), through which it shall synthesise and extract expressions from *f-string* literals, and then reassemble the original string using `str.format` method. Besides **[conversion](https://docs.python.org/3/library/string.html#format-string-syntax)** and **[format specification](https://docs.python.org/3/library/string.html#formatspec)**, `f2format` also considered and resolved **[string concatenation](https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation)**. Also, it always tries to maintain the original layout of source code, and accuracy of syntax.

## Installation

> Note that `f2format` only supports Python versions __since 3.6__

&emsp; Simply run the following to install the current version from PyPI:

```sh
pip install f2format
```

&emsp; Or install the latest version from the git repository:

```sh
git clone https://github.com/JarryShaw/f2format.git
cd f2format
pip install -e .
# and to update at any time
git pull
```

## Usage

&emsp; It is fairly straightforward to use `f2format`:

```
f2format 0.1.2
usage: f2format [-h] [-n] <python source files and folders..>

Convert f-string to str.format for Python 3 compatibility.

options:
    -h      show this help message and exit
    -n      do not archive original files
```

&emsp; `f2format` will read then convert all *f-string* literals in every Python file under this path. In case there might be some problems with the conversion, `f2format` will duplicate all original files it is to modify into `archive` directory ahead of the process, if `-n` not set.

## Contribution

&emsp; Contributions are very welcome, especially fixing bugs and providing test cases, which [@gousaiyang](https://github.com/gousaiyang) is to help with, so to speak. Note that code must remain valid and reasonable.
