API Reference
=============

.. module:: poseur

.. .. automodule:: poseur
..    :members:
..    :undoc-members:
..    :show-inheritance:

Public Interface
----------------

.. autofunction:: poseur.convert

.. autofunction:: poseur.poseur

.. autofunction:: poseur.main

Exported Decorator
------------------

As you may wish to provide runtime positional-only parameter checks for
your own code, ``poseur`` exposed the decorator function for developers
to use by themselves.

.. autofunction:: poseur.decorator

Conversion Implementation
-------------------------

The main logic of the ``poseur`` conversion is to

For conversion algorithms and details, please refer to :doc:`algorithms`.

Conversion Templates
~~~~~~~~~~~~~~~~~~~~

For general conversion scenarios, the converted wrapper functions will be
rendered based on the following templates.

Conversion Contexts
~~~~~~~~~~~~~~~~~~~

.. autoclass:: poseur.Context
   :members:
   :undoc-members:
   :private-members:
   :show-inheritance:

.. autoclass:: poseur.StringContext
   :members:
   :undoc-members:
   :private-members:
   :show-inheritance:

Internal Auxiliaries
--------------------

Options & Defaults
~~~~~~~~~~~~~~~~~~

.. autodata:: poseur.poseur_SOURCE_VERSIONS

Below are option getter utility functions. Option value precedence is::

   explicit value (CLI/API arguments) > environment variable > default value

.. autofunction:: poseur._get_quiet_option
.. autofunction:: poseur._get_concurrency_option
.. autofunction:: poseur._get_do_archive_option
.. autofunction:: poseur._get_archive_path_option
.. autofunction:: poseur._get_source_version_option
.. autofunction:: poseur._get_linesep_option
.. autofunction:: poseur._get_indentation_option
.. autofunction:: poseur._get_pep8_option

The following variables are used for fallback default values of options.

.. autodata:: poseur._default_quiet
.. autodata:: poseur._default_concurrency
.. autodata:: poseur._default_do_archive
.. autodata:: poseur._default_archive_path
.. autodata:: poseur._default_source_version
.. autodata:: poseur._default_linesep
.. autodata:: poseur._default_indentation
.. autodata:: poseur._default_pep8

.. important::

   For :data:`_default_concurrency`, :data:`_default_linesep` and :data:`_default_indentation`,
   :data:`None` means *auto detection* during runtime.

CLI Utilities
~~~~~~~~~~~~~

.. autofunction:: poseur.get_parser

The following variables are used for help messages in the argument parser.

.. data:: poseur.__cwd__
   :type: str

   Current working directory returned by :func:`os.getcwd`.

.. data:: poseur.__poseur_quiet__
   :type: Literal[\'quiet mode\', \'non-quiet mode\']

   Default value for the ``--quiet`` option.

   .. seealso:: :func:`poseur._get_quiet_option`

.. data:: poseur.__poseur_concurrency__
   :type: Union[int, Literal[\'auto detect\']]

   Default value for the ``--concurrency`` option.

   .. seealso:: :func:`poseur._get_concurrency_option`

.. data:: poseur.__poseur_do_archive__
   :type: Literal[\'will do archive\', \'will not do archive\']

   Default value for the ``--no-archive`` option.

   .. seealso:: :func:`poseur._get_do_archive_option`

.. data:: poseur.__poseur_archive_path__
   :type: str

   Default value for the ``--archive-path`` option.

   .. seealso:: :func:`poseur._get_archive_path_option`

.. data:: poseur.__poseur_source_version__
   :type: str

   Default value for the ``--source-version`` option.

   .. seealso:: :func:`poseur._get_source_version_option`

.. data:: poseur.__poseur_linesep__
   :type: Literal[\'LF\', \'CRLF\', \'CR\', \'auto detect\']

   Default value for the ``--linesep`` option.

   .. seealso:: :func:`poseur._get_linesep_option`

.. data:: poseur.__poseur_indentation__
   :type: str

   Default value for the ``--indentation`` option.

   .. seealso:: :func:`poseur._get_indentation_option`

.. data:: poseur.__poseur_pep8__
   :type: Literal[\'will conform to PEP 8\', \'will not conform to PEP 8\']

   Default value for the ``--no-pep8`` option.

   .. seealso:: :func:`poseur._get_pep8_option`
