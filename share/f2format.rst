========
f2format
========

---------------------------------------------------
back-port compiler for Python 3.6 f-string literals
---------------------------------------------------

:Version: v0.8.6
:Date: December 11, 2019
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

This man page mainly introduces the CLI options of the ``f2format`` program.
You can also checkout the online documentation at
https://bpc-f2format.readthedocs.io/ for more details.

OPTIONS
=======

positional arguments
--------------------

:SOURCE:                Python source files and directories to be converted

optional arguments
------------------

-h, --help              show this help message and exit
-V, --version           show program's version number and exit
-q, --quiet             run in quiet mode

-C *N*, --concurrency *N*
                        the number of concurrent processes for conversion

--dry-run               list the files to be converted without actually performing conversion and archiving

-s *[FILE]*, --simple *[FILE]*
                        this option tells the program to operate in "simple mode"; if a file name is provided, the program will convert
                        the file but print conversion result to standard output instead of overwriting the file; if no file names are
                        provided, read code for conversion from standard input and print conversion result to standard output; in
                        "simple mode", no file names shall be provided via positional arguments

archive options
---------------

backup original files in case there're any issues

-na, --no-archive       do not archive original files

-k *PATH*, --archive-path *PATH*
                        path to archive original files

-r *ARCHIVE_FILE*, --recover *ARCHIVE_FILE*
                        recover files from a given archive file

-r2                     remove the archive file after recovery
-r3                     remove the archive file after recovery, and remove the archive directory if it becomes empty

convert options
---------------

conversion configuration

-vs *VERSION*, --vf *VERSION*, --source-version *VERSION*, --from-version *VERSION*
                        parse source code as this Python version

-l *LINESEP*, --linesep *LINESEP*
                        line separator (**LF**, **CRLF**, **CR**) to read source files

-t *INDENT*, --indentation *INDENT*
                        code indentation style, specify an integer for the number of spaces, or ``'t'``/``'tab'`` for tabs

-n8, --no-pep8          do not make code insertion **PEP 8** compliant

ENVIRONMENT
===========

``f2format`` currently supports three environment variables.

:F2FORMAT_QUIET:          run in quiet mode
:F2FORMAT_CONCURRENCY:    the number of concurrent processes for conversion
:F2FORMAT_DO_ARCHIVE:     whether to perform archiving
:F2FORMAT_ARCHIVE_PATH:   path to archive original files
:F2FORMAT_SOURCE_VERSION: parse source code as this Python version
:F2FORMAT_LINESEP:        line separator to read source files
:F2FORMAT_INDENTATION:    code indentation style
:F2FORMAT_PEP8:           whether to make code insertion **PEP 8** compliant

SEE ALSO
========

pybpc(1), poseur(1), walrus(1), vermin(1)
