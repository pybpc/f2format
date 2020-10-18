Usage
=====

Specifying Files And Directories To Convert
-------------------------------------------

To convert a single file:

.. code-block:: console

   $ cat myscript.py
   print(hello := 'world')
   $ poseur myscript.py
   Now converting: '/path/to/project/myscript.py'
   $ cat myscript.py  # file overwritten with conversion result
   if False:
       hello = NotImplemented


   def __poseur_wrapper_hello_5adbf5ee911449cba75e35b9ef97ea80(expr):
       """Wrapper function for assignment expression."""
       global hello
       hello = expr
       return hello


   print(__poseur_wrapper_hello_5adbf5ee911449cba75e35b9ef97ea80('world'))


To convert the whole project at the current working directory (overwrites all
Python source files inside):

.. code-block:: console

   $ poseur .

Multiple files and directories may be supplied at the same time:

.. code-block:: console

   $ poseur script_without_py_extension /path/to/another/project

.. note::

   When converting a directory, ``poseur`` will recursively find all the
   Python source files in the directory (and its subdirectories, if any).
   Whether a file is a Python source file is determined by its file extension
   (``.py`` or ``.pyw``). If you want to convert a file without a Python
   extension, you will need to explicitly specify it in the argument list.

If you prefer a side-effect free behavior (do not overwrite files), you can
use the **simple mode**.

Simple mode with no arguments (read from stdin, write to stdout):

.. code-block:: console

   $ printf 'print(hello := "world")\n' | python3 poseur.py -s
   if False:
       hello = NotImplemented


   def __poseur_wrapper_hello_fbf3a9dabd2b40348815e3f2b22a1683(expr):
       """Wrapper function for assignment expression."""
       global hello
       hello = expr
       return hello

   print(__poseur_wrapper_hello_fbf3a9dabd2b40348815e3f2b22a1683("world"))

Simple mode with a file name argument (read from file, write to stdout):

.. code-block:: console

   $ cat myscript.py
   print(hello := 'world')
   $ poseur -s myscript.py
   if False:
       hello = NotImplemented


   def __poseur_wrapper_hello_d1e6c2a11a76400aa9745bd90b3fb52a(expr):
       """Wrapper function for assignment expression."""
       global hello
       hello = expr
       return hello

   print(__poseur_wrapper_hello_d1e6c2a11a76400aa9745bd90b3fb52a('world'))
   $ cat myscript.py
   print(hello := 'world')

In simple mode, no file names shall be provided via positional arguments.

Archiving And Recovering Files
------------------------------

If you are not using the simple mode, ``poseur`` overwrites Python source
files, which could potentially cause data loss. Therefore, a built-in archiving
functionality is enabled by default. The original copies of the Python source
files to be converted will be packed into an archive file and placed under the
``archive`` subdirectory of the current working directory.

To opt out of archiving, use the CLI option ``-na`` (``--no-archive``), or set
environment variable ``POSEUR_DO_ARCHIVE=0``.

To use an alternative name for the archive directory (other than ``archive``),
use the CLI option ``-k`` (``--archive-path``), or set the environment
variable ``POSEUR_ARCHIVE_PATH``.

To recover files from an archive file, use the CLI option ``-r``
(``--recover``):

.. code-block:: console

   $ poseur -r archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz
   Recovered files from archive: 'archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz'
   $ ls archive/
   archive-20200814222751-f3a514d40d69c6d5.tar.gz

By default, the archive file is still retained after recovering from it. If you
would like it to be removed after recovery, specify the CLI option ``-r2``:

.. code-block:: console

   $ poseur -r archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz -r2
   Recovered files from archive: 'archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz'
   $ ls archive/

If you also want to remove the archive directory if it becomes empty, specify
the CLI option ``-r3``:

.. code-block:: console

   $ poseur -r archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz -r3
   Recovered files from archive: 'archive/archive-20200814222751-f3a514d40d69c6d5.tar.gz'
   $ ls archive/
   ls: cannot access 'archive/': No such file or directory

.. warning::

   To improve stability of file recovery, the archive file records the original
   absolute paths of the Python source files. Thus, file recovery is only
   guaranteed to work correctly on **the same machine** where the archive file
   was created. Never perform the recovery operation on an arbitrary untrusted
   archive file. Doing so may allow attackers to overwrite any files in the
   system.

Conversion Options
------------------

By default, ``poseur`` automatically detects file line endings and use the
same line ending for code insertion. If you want to manually specify the line
ending to be used, use the CLI option ``-l`` (``--linesep``) or the
``POSEUR_LINESEP`` environment variable.

By default, ``poseur`` automatically detects file indentations and use the
same indentation for code insertion. If you want to manually specify the
indentation to be used, use the CLI option ``-t`` (``--indentation``) or the
``POSEUR_INDENTATION`` environment variable.

By default, ``poseur`` parse Python source files as the latest version.
If you want to manually specify a version for parsing, use the CLI option
``-vs`` (``-vf``, ``--source-version``, ``--from-version``) or the
``POSEUR_SOURCE_VERSION`` environment variable.

By default, code insertion of ``poseur`` conforms to :pep:`8`. To opt out
and get a more compact result, specify the CLI option ``-n8`` (``--no-pep8``)
or set environment variable ``POSEUR_PEP8=0``.

Runtime Options
---------------

Specify the CLI option ``-q`` (``--quiet``) or set environment variable
``POSEUR_QUIET=1`` to run in quiet mode.

Specify the CLI option ``-C`` (``--concurrency``) or set environment variable
``POSEUR_CONCURRENCY`` to specify the number of concurrent worker processes
for conversion.

Use the ``--dry-run`` CLI option to list the files to be converted without
actually performing conversion and archiving.

By running ``poseur --help``, you can see the current values of all the options,
based on their default values and your environment variables.

API Usage
---------

If you want to programmatically invoke ``poseur``, you may want to look at
:doc:`api`. The :func:`poseur.convert` and :func:`poseur.poseur`
functions should be most commonly used.

Disutils/Setuptools Integration
-------------------------------

``poseur`` can also be directly integrated within your ``setup.py`` script
to dynamically convert *assignment expressions* upon installation:

.. code-block:: python
   :emphasize-lines: 21,33,36

   import subprocess
   import sys

   try:
       from setuptools import setup
       from setuptools.command.build_py import build_py
   except ImportError:
       from distutils.core import setup
       from distutils.command.build_py import build_py

   version_info = sys.version_info[:2]


   class build(build_py):
       """Add on-build backport code conversion."""

       def run(self):
           if version_info < (3, 8):
               try:
                   subprocess.check_call(  # nosec
                       [sys.executable, '-m', 'poseur', '--no-archive', 'PACKAGENAME']
                   )
               except subprocess.CalledProcessError as error:
                   print('Failed to perform assignment expression backport compiling.'
                         'Please consider manually install `bpc-poseur` and try again.', file=sys.stderr)
                   sys.exit(error.returncode)
           build_py.run(self)


   setup(
       ...
       setup_requires=[
           'bpc-poseur; python_version < "3.8"',
       ],
       cmdclass={
           'build_py': build,
       },
   )

Or, as :pep:`518` proposed, you may simply add ``bpc-poseur`` to
the ``requires`` list from the ``[build-system]`` section in the
``pyproject.toml`` file:

.. code-block:: toml
   :emphasize-lines: 3

   [built-system]
   # Minimum requirements for the build system to execute.
   requires = ["setuptools", "wheel", "bpc-poseur"]  # PEP 508 specifications.
   ...
