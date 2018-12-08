# Changelog

## Version 0.4.0.post1

 > Release date: 2018-12-08

&emsp; There were no new changes in version 0.4.0.post1.

## Version 0.4.0

 > Release date: 2018-12-08

- no changes
- changed license and updated misc files

## Version 0.3.1

 > Release date: 2018-11-29

- revised CLI, introduced `argparse`
- fixed compatibility issue when given files not encoded with 'UTF-8'
- now supports customise archive path & file encoding

## Version 0.3.0

 > Release date: 2018-11-28

- restructured f2format
- fixed crash errors when archiving files with folder prefix
- fixed abnormal behaviour using in CPython 3.4/3.5

## Version 0.2.4

 > Release date: 2018-11-28

&emsp; Fixed distribution errors, and uploaded CPython 3.4/3.5 wheels.

## Version 0.2.3.post1

 > Release date: 2018-11-27

&emsp; There were no new changes in version 0.2.3.post1.

## Version 0.2.3

 > Release date: 2018-11-27

&emsp; There were no new changes in version 0.2.3, except:

- `f2format` available from Homebrew
- revised distro scripts
- updated README.md

## Version 0.2.2

 > Release date: 2018-11-27

&emsp; Fixed bugs when stripping leading *f-string* literals (\[fF\]).

## Version 0.2.1.post2

 > Release date: 2018-11-25

&emsp; There were no new changes in version 0.2.1.post2.

## Version 0.2.1.post1

 > Release date: 2018-11-25

&emsp; There were no new changes in version 0.2.1.post1.

## Version 0.2.1

 > Release date: 2018-11-17

&emsp; There were no new changes in version 0.2.1.

## Version 0.2.0.post3

 > Release date: 2018-11-17

&emsp; There were no new changes in version 0.2.0.post3.

## Version 0.2.0.post2

 > Release date: 2018-11-13

&emsp; There were no new changes in version 0.2.0.post2.

## Version 0.2.0.post1

 > Release date: 2018-11-12

&emsp; There were no new changes in version 0.2.0.post1.

## Version 0.2.0

 > Release date: 2018-11-12

- pep8 compatible
- updated test samples
- now supports up from Python 3.3

## Version 0.1.4

 > Release date: 2018-09-17

- removed redundant parentheses according to u/ziel from Reddit

## Version 0.1.3.post2

 > Release date: 2018-09-17

&emsp; There were no new changes in version 0.1.3.post2.

## Version 0.1.3.post1

 > Release date: 2018-09-16

&emsp; There were no new changes in version 0.1.3.post1.

## Version 0.1.3

 > Release date: 2018-09-16

&emsp; Now `f2format` supports all encodings, including emoji!

- introduced mutable `strarray`
- revised conversion process
- changed archive algorithm
- fixed minor bugs

## Version 0.1.2

 > Release date: 2018-09-16

- considered when `multiprocessing` not supported
- revised search algorithm for end of *f-string* expressions
- revised length calculation of *f-string* raw string part
- renamed functions
- fixed minor bugs

## Version 0.1.1

 > Release date: 2018-09-16

- fixed bugs when try exclusively due to quote characters
- avoided infinite loop
- fixed bugs when token is `NL`
- fixed bugs when expression is implicit tuple
- fixed bugs when counting braces `'{}'` in ast.Str
- fixed bugs when archiving files

## Version 0.1.0 (initial distribution)

 > Release date: 2018-09-15

&emsp; There were no new changes in version 0.1.0.

## Version 0.1.0b2

 > Release date: 2018-09-15

- fixed minor bugs
- comments added

## Version 0.1.0b1

 > Release date: 2018-09-15

&emsp; Convert *f-string* to `str.format` for Python 3 compatibility.
