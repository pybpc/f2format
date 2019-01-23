# f2format

 > Write *f-string* in Python 3.6 flavour, and let `f2format` worry about back-port issues :beer:

&emsp; Since [PEP 498](https://www.python.org/dev/peps/pep-0498/), Python introduced
*[f-string](https://docs.python.org/3/reference/lexical_analysis.html#formatted-string-literals)*
literal in version __3.6__. Though released ever since
[December 23, 2016](https://docs.python.org/3.6/whatsnew/changelog.html#python-3-6-0-final), Python
3.6 is still not widely used as expected. For those who are now used to *f-string*, `f2format`
provides an intelligent, yet imperfect, solution of a **backport compiler** by converting
*f-string*s to `str.format` literals, which guarantees you to always write *f-string* in Python
3.6 flavour then compile for compatibility later.

&emsp; `f2format` is inspired and assisted by my mate [@gousaiyang](https://github.com/gousaiyang).
It functions by tokenising and parsing Python code into multiple abstract syntax trees (AST),
through which it shall synthesise and extract expressions from *f-string* literals, and then
reassemble the original string using `str.format` method. Besides
**[conversion](https://docs.python.org/3/library/string.html#format-string-syntax)** and
**[format specification](https://docs.python.org/3/library/string.html#formatspec)**, `f2format`
also considered and resolved
**[string concatenation](https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation)**.
Also, it always tries to maintain the original layout of source code, and accuracy of syntax.

## Installation

> Note that `f2format` only supports Python versions __since 3.3__

&emsp; For macOS users, `f2format` is now available through [Homebrew](https://brew.sh):

```sh
brew tap jarryshaw/tap
brew install f2format
# or simply, a one-liner
brew install jarryshaw/tap/f2format
```

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

### CLI

&emsp; It is fairly straightforward to use `f2format`:

 > context in `${...}` changes dynamically according to runtime environment

```man
usage: f2format [options] <python source files and folders...>

Convert f-string to str.format for Python 3 compatibility.

positional arguments:
  SOURCE                python source files and folders to be converted
                        (default is '${CWD}')

optional arguments:
  -h, --help            show this help message and exit
  -V, --version         show program's version number and exit

archive options:
  duplicate original files in case there's any issue

  -n, --no-archive      do not archive original files
  -p PATH, --archive-path PATH
                        path to archive original files (default is '${CWD}/archive')

convert options:
  compatibility configuration for none-unicode files

  -c CODING, --encoding CODING
                        encoding to open source files (default is '${ENCODING}')
```

&emsp; `f2format` will read then convert all *f-string* literals in every Python file under this
path. In case there might be some problems with the conversion, `f2format` will duplicate all
original files it is to modify into `archive` directory ahead of the process, if `-n` not set.

&emsp; For instance, the code will be converted as follows.

```python
# the original code
var = f'foo{(1+2)*3:>5}bar{"a", "b"!r}boo'
# after `f2format`
var = 'foo{:>5}bar{!r}boo'.format((1+2)*3, ("a", "b"))
```

### Automator

&emsp; [`make-demo.sh`](https://github.com/JarryShaw/f2format/blob/master/make-demo.sh) provides a
demo script, which may help integrate `f2format` in your development and distribution circle.

 > __NB__: `make-demo.sh` is not an integrated automation script. It should be revised by design.

&emsp; It assumes

- all source files in `/src` directory
- using GitHub for repository management
- having **release** branch under `/release` directory
- already installed `f2format` and [`twine`](https://github.com/pypa/twine#twine)
- permission to these files and folders granted

&emsp; And it will

- copy `setup.py` and `src` to `release` directory
- run `f2format` for Python files under `release`
- distribute to [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org) using `twine`
- upload to release branch on GitHub
- upload original files to GitHub

### APIs

```python
f2format.f2format(filename)
```

 > Wrapper works for conversion.

Args:

- `filename` -- `str`, file to be converted

```python
f2format.convert(string, lineno)
```

 > The main conversion process.

Args:

- `string` -- `str`, context to be converted
- `lineno` -- `dict<int: int>`, line number to actual offset mapping

Returns:

- `str` -- converted string

### Codec

&emsp; [`f2format-codec`](https://github.com/JarryShaw/f2format-codec) registers a codec in Python
interpreter, which grants you the compatibility to write directly in Python 3.6 *f-string* syntax
even through running with a previous version of Python.

## Test

&emsp; The current test samples are under [`/test`](https://github.com/JarryShaw/f2format/blob/master/test)
folder. `test_driver.py` is the main entry point for tests.

## Contribution

&emsp; Contributions are very welcome, especially fixing bugs and providing test cases, which
[@gousaiyang](https://github.com/gousaiyang) is to help with, so to speak. Note that code must
remain valid and reasonable.
