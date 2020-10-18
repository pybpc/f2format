.. poseur documentation master file, created by
   sphinx-quickstart on Sat Apr 11 11:06:46 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

``poseur`` - Backport Compiler for Positional-only Parameters
=============================================================

   Write *positional-only parameters* in Python 3.8 flavour, and let ``poseur`` worry about back-port issues |:beer:|

Since :pep:`570`, Python introduced *positional-only parameters* syntax in version **3.8**. For those who wish to use
*positional-only parameters* in their code, ``poseur`` provides an intelligent, yet imperfect, solution of a
**backport compiler** by replacing *positional-only parameters* syntax with old-fashioned syntax, which guarantees
you to always write *positional-only parameters* in Python 3.8 flavour then compile for compatibility later.

.. toctree::
   :maxdepth: 3

   usage
   algorithms
   api

------------
Installation
------------

.. note::

   ``poseur`` only supports Python versions **since 3.4** |:snake:|

For macOS users, ``poseur`` is available through `Homebrew`_:

.. code-block:: shell

   brew tap jarryshaw/tap
   brew install poseur
   # or simply, a one-liner
   brew install jarryshaw/tap/poseur

You can also install from `PyPI`_ for any OS:

.. code-block:: shell

   pip install bpc-poseur

Or install the latest version from the `Git repository`_:

.. code-block:: shell

   git clone https://github.com/pybpc/poseur.git
   cd poseur
   pip install -e .
   # and to update at any time
   git pull

.. note::
   Installation from `Homebrew`_ will also automatically install the man page and
   `Bash Completion`_ script for you. If you are installing from `PyPI`_ or
   the `Git repository`_, you can install the completion script manually.

.. _Homebrew: https://brew.sh
.. _PyPI: https://pypi.org/project/python-poseur
.. _Git repository: https://github.com/pybpc/poseur
.. _Bash Completion: https://github.com/pybpc/poseur/blob/master/share/poseur.bash-completion

-----
Usage
-----

See :doc:`usage`.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
