Algorithms
==========

As discussed in :pep:`498`, *formatted string literals* (*f-string*) is a way to
interpolate evaluated expression values into regular string literals, using the syntax
``f ' <text> { <expression> <optional !s, !r, or !a> <optional : format specifier> } <text> ... '``.
It is roughly equivalent to first evaluate the value of ``expression`` then
interpolate its value into the string literal with provided format specifiers and
convension.

Basic Concepts
--------------

To convert, ``f2format`` will first extract all *expressions* from the *f-strings*,
then rewrite the literal with a ``str.format`` function using anonymous positional
expression sequence from the extracted expressions.

For example, with the samples from :pep:`498`:

.. code-block:: python

   f'abc{expr1:spec1}{expr2!r:spec2}def{expr3}ghi'

it should be converted to

.. code-block:: python

   'abc{:spec1}{:spec2}def{}ghi'.format(expr1, expr2, expr3)

Concatenable Strings
--------------------

As mentioned in the `Python documentation <https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation>`__,
multiple adjacent string or bytes literals (delimited by whitespace), possibly
using different quoting conventions, are allowed, and their meaning is the same as
their concatenation.

In cases where a *f-string* can be found in such sequence of concatenable strings,
directly converting the *f-string* to ``str.format`` syntax may cause the concatenation
to be broken. Therefore, ``f2format`` will rather insert the converted ``.format`` call
at the end of the string sequence.

For example, a sequence of concatenable strings may be as follows:

.. code-block:: python

   ('/usr/local/opt/python/bin/python3.7 -c "'
    'import re, sys\n'
    'for line in sys.stdin:\n'
    "    data = line.rstrip().replace('^D\x08\x08', '')\n"
    "    temp = re.sub(r'\x1b\\[[0-9][0-9;]*m', r'', data, flags=re.IGNORECASE)\n"
    f"    text = temp.replace('Password:', 'Password:\\r\\n'){_replace(password)}\n"
    '    if text:\n'
    "        print(text, end='\\r\\n')\n"
    '"')

then ``f2format`` will convert the code above as

.. code-block:: python

   ('/usr/local/opt/python/bin/python3.7 -c "'
    'import re, sys\n'
    'for line in sys.stdin:\n'
    "    data = line.rstrip().replace('^D\x08\x08', '')\n"
    "    temp = re.sub(r'\x1b\\[[0-9][0-9;]*m', r'', data, flags=re.IGNORECASE)\n"
    "    text = temp.replace('Password:', 'Password:\\r\\n'){}\n"
    '    if text:\n'
    "        print(text, end='\\r\\n')\n"
    '"'.format(_replace(password)))

Debug F-Strings
---------------

Since Python 3.8, ``=`` was introduced to *f-strings* in addition to the acceptance
of `bpo-36817 <https://bugs.python.org/issue36817>`__. As discussed in the
`Python documentation <https://docs.python.org/3/reference/lexical_analysis.html#formatted-string-literals>`__,
when the equal sign ``'='`` is provided, the output will have the expression text,
the ``'='`` and the evaluated value, therefore ``f2format`` tend to keep an original
copy of the expressions in the converted strings then append ``str.format`` with
corresponding expressions.

For a *f-string* as below:

.. code-block:: python

   >>> foo = "bar"
   >>> f"{ foo = }" # preserves whitespace
   " foo = 'bar'"

``f2format`` will convert it as

.. code-block:: python

   " foo = {!r}".format(foo)
