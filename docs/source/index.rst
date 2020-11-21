.. f2format documentation master file, created by
   sphinx-quickstart on Sat Apr 11 11:06:46 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

``f2format`` - Backport Compiler for Formatted String Literals
==============================================================

   Write *formatted string literals* in Python 3.8 flavour, and let ``f2format`` worry about back-port issues |:beer:|

Since :pep:`498`, Python introduced *formatted string literals* syntax in version **3.6**. For those who wish to use
*formatted string literals* in their code, ``f2format`` provides an intelligent, yet imperfect, solution of a
**backport compiler** by replacing *formatted string literals* syntax with old-fashioned syntax, which guarantees
you to always write *formatted string literals* in Python 3.8 flavour then compile for compatibility later.

.. toctree::
   :maxdepth: 3

   usage
   algorithms
   api

------------
Installation
------------

.. warning::

   ``f2format`` is currently under reconstruction. It is highly recommended to directly install
   from the git repo or the pre-release distributions.

.. note::

   ``f2format`` only supports Python versions **since 3.4** |:snake:|

For macOS users, ``f2format`` is available through `Homebrew`_:

.. code-block:: shell

   brew tap jarryshaw/tap
   brew install f2format
   # or simply, a one-liner
   brew install jarryshaw/tap/f2format

You can also install from `PyPI`_ for any OS:

.. code-block:: shell

   pip install bpc-f2format

Or install the latest version from the `Git repository`_:

.. code-block:: shell

   git clone https://github.com/pybpc/f2format.git
   cd f2format
   pip install -e .
   # and to update at any time
   git pull

.. note::
   Installation from `Homebrew`_ will also automatically install the man page and
   `Bash Completion`_ script for you. If you are installing from `PyPI`_ or
   the `Git repository`_, you can install the completion script manually.

.. _Homebrew: https://brew.sh
.. _PyPI: https://pypi.org/project/python-f2format
.. _Git repository: https://github.com/pybpc/f2format
.. _Bash Completion: https://github.com/pybpc/f2format/blob/master/share/f2format.bash-completion

-----
Usage
-----

See :doc:`usage`.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
