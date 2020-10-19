API Reference
=============

.. module:: f2format

.. .. automodule:: f2format
..    :members:
..    :undoc-members:
..    :show-inheritance:

Public Interface
----------------

.. autofunction:: f2format.convert

.. autofunction:: f2format.f2format

.. autofunction:: f2format.main

Exported Decorator
------------------

As you may wish to provide runtime positional-only parameter checks for
your own code, ``f2format`` exposed the decorator function for developers
to use by themselves.

.. autofunction:: f2format.decorator

Conversion Implementation
-------------------------

The main logic of the ``f2format`` conversion is to extract the expressions
part from *formatted string literals* and rewrite the original *f-string*
using ``str.format`` syntax.

For conversion algorithms and details, please refer to :doc:`algorithms`.

.. autoclass:: f2format.Context
   :members:
   :undoc-members:
   :private-members:
   :show-inheritance:

.. autoclass:: f2format.StringContext
   :members:
   :undoc-members:
   :private-members:
   :show-inheritance:

Options & Defaults
~~~~~~~~~~~~~~~~~~

.. autodata:: f2format.f2format_SOURCE_VERSIONS

Below are option getter utility functions. Option value precedence is::

   explicit value (CLI/API arguments) > environment variable > default value

.. autofunction:: f2format._get_quiet_option
.. autofunction:: f2format._get_concurrency_option
.. autofunction:: f2format._get_do_archive_option
.. autofunction:: f2format._get_archive_path_option
.. autofunction:: f2format._get_source_version_option
.. autofunction:: f2format._get_linesep_option
.. autofunction:: f2format._get_indentation_option
.. autofunction:: f2format._get_pep8_option

The following variables are used for fallback default values of options.

.. autodata:: f2format._default_quiet
.. autodata:: f2format._default_concurrency
.. autodata:: f2format._default_do_archive
.. autodata:: f2format._default_archive_path
.. autodata:: f2format._default_source_version
.. autodata:: f2format._default_linesep
.. autodata:: f2format._default_indentation
.. autodata:: f2format._default_pep8

.. important::

   For :data:`_default_concurrency`, :data:`_default_linesep` and :data:`_default_indentation`,
   :data:`None` means *auto detection* during runtime.

CLI Utilities
~~~~~~~~~~~~~

.. autofunction:: f2format.get_parser

The following variables are used for help messages in the argument parser.

.. data:: f2format.__cwd__
   :type: str

   Current working directory returned by :func:`os.getcwd`.

.. data:: f2format.__f2format_quiet__
   :type: Literal[\'quiet mode\', \'non-quiet mode\']

   Default value for the ``--quiet`` option.

   .. seealso:: :func:`f2format._get_quiet_option`

.. data:: f2format.__f2format_concurrency__
   :type: Union[int, Literal[\'auto detect\']]

   Default value for the ``--concurrency`` option.

   .. seealso:: :func:`f2format._get_concurrency_option`

.. data:: f2format.__f2format_do_archive__
   :type: Literal[\'will do archive\', \'will not do archive\']

   Default value for the ``--no-archive`` option.

   .. seealso:: :func:`f2format._get_do_archive_option`

.. data:: f2format.__f2format_archive_path__
   :type: str

   Default value for the ``--archive-path`` option.

   .. seealso:: :func:`f2format._get_archive_path_option`

.. data:: f2format.__f2format_source_version__
   :type: str

   Default value for the ``--source-version`` option.

   .. seealso:: :func:`f2format._get_source_version_option`

.. data:: f2format.__f2format_linesep__
   :type: Literal[\'LF\', \'CRLF\', \'CR\', \'auto detect\']

   Default value for the ``--linesep`` option.

   .. seealso:: :func:`f2format._get_linesep_option`

.. data:: f2format.__f2format_indentation__
   :type: str

   Default value for the ``--indentation`` option.

   .. seealso:: :func:`f2format._get_indentation_option`

.. data:: f2format.__f2format_pep8__
   :type: Literal[\'will conform to PEP 8\', \'will not conform to PEP 8\']

   Default value for the ``--no-pep8`` option.

   .. seealso:: :func:`f2format._get_pep8_option`
