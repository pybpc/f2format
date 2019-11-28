========
f2format
========

---------------------------------------------------
back-port compiler for Python 3.6 f-string literals
---------------------------------------------------

:Version: v0.8.5.post1
:Date: November 28, 2019
:Manual section: 1
:Author:
    Jarry Shaw, a newbie programmer, is the author, owner and maintainer
    of *f2format*. Please contact me at *jarryshaw@icloud.com*.
:Copyright:
    *f2format* is licensed under the **Apache Software License**.

SYNOPSIS
========

f2format [*options*] <*python source files and folders*> ...

DESCRIPTION
===========

Since PEP 498, Python introduced *f-string* literal in version __3.6__. Though
released ever since December 23, 2016, Python 3.6 is still not widely used as
expected. For those who are now used to *f-string*, ``f2format`` provides an
intelligent, yet imperfect, solution of a **backport compiler** by converting
*f-string*s to ``str.format`` literals, which guarantees you to always write
*f-string* in Python 3.6 flavour then compile for compatibility later.

``f2format`` functions by tokenising and parsing Python code into multiple
abstract syntax trees (AST), through which it shall synthesise and extract
expressions from *f-string* literals, and then reassemble the original string
using ``str.format`` method. Besides **conversion** and **format specification**,
``f2format`` also considered and resolved **string concatenation**. Also, it always
tries to maintain the original layout of source code, and accuracy of syntax.

OPTIONS
=======

positional arguments
--------------------

:SOURCE:              python source files and folders to be converted

optional arguments
------------------

-h, --help            show this help message and exit
-V, --version         show program's version number and exit
-q, --quiet           run in quiet mode

archive options
---------------

duplicate original files in case there's any issue

-na, --no-archive     do not archive original files

-p *PATH*, --archive-path *PATH*
                      path to archive original files

convert options
---------------

compatibility configuration for none-unicode files

-c *CODING*, --encoding *CODING*
                      encoding to open source files

-v *VERSION*, --python *VERSION*
                      convert against Python version

ENVIRONMENT
===========

``f2format`` currently supports three environment variables.

:F2FORMAT_ENCODING:   encoding to open source files
:F2FORMAT_VERSION:    convert against Python version
:F2FORMAT_QUIET:      run in quiet mode

SEE ALSO
========

babel(1), poseur(1), walrus(1), vermin(1)
