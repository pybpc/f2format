# -*- coding: utf-8 -*-
"""Back-port compiler for Python 3.6 f-string literals."""

import argparse
import os
import pathlib
import re
import sys
import traceback
from typing import Generator, List, Optional, Union

import parso.python.tree
import parso.tree
import tbtrim
from bpc_utils import (BaseContext, BPCSyntaxError, Config, TaskLock, archive_files,
                       detect_encoding, detect_files, detect_indentation, detect_linesep,
                       first_non_none, get_parso_grammar_versions, map_tasks, parse_boolean_state,
                       parse_indentation, parse_linesep, parse_positive_integer, parso_parse,
                       recover_files)
from bpc_utils.typing import Linesep
from typing_extensions import ClassVar, Final, Literal, final

__all__ = ['main', 'f2format', 'convert']  # pylint: disable=undefined-all-variable

# version string
__version__ = '0.8.7rc1'

###############################################################################
# Typings


class F2formatConfig(Config):
    indentation = ''  # type: str
    linesep = '\n'  # type: Literal[Linesep]
    pep8 = True  # type: bool
    filename = None  # Optional[str]
    source_version = None  # Optional[str]


##############################################################################
# Auxiliaries

#: Get supported source versions.
#:
#: .. seealso:: :func:`bpc_utils.get_parso_grammar_versions`
F2FORMAT_SOURCE_VERSIONS = get_parso_grammar_versions(minimum='3.6')

# option default values
#: Default value for the ``quiet`` option.
_default_quiet = False
#: Default value for the ``concurrency`` option.
_default_concurrency = None  # auto detect
#: Default value for the ``do_archive`` option.
_default_do_archive = True
#: Default value for the ``archive_path`` option.
_default_archive_path = 'archive'
#: Default value for the ``source_version`` option.
_default_source_version = F2FORMAT_SOURCE_VERSIONS[-1]
#: Default value for the ``linesep`` option.
_default_linesep = None  # auto detect
#: Default value for the ``indentation`` option.
_default_indentation = None  # auto detect
#: Default value for the ``pep8`` option.
_default_pep8 = True

# option getter utility functions
# option value precedence is: explicit value (CLI/API arguments) > environment variable > default value


def _get_quiet_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``quiet`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``quiet`` option

    :Environment Variables:
        :envvar:`F2FORMAT_QUIET` -- the value in environment variable

    See Also:
        :data:`_default_quiet`

    """
    # We need lazy evaluation, so first_non_none(a, b, c) does not work here
    # with PEP 505 we can simply write a ?? b ?? c
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('F2FORMAT_QUIET'))
        yield _default_quiet
    return first_non_none(_option_layers())


def _get_concurrency_option(explicit: Optional[int] = None) -> Optional[int]:
    """Get the value for the ``concurrency`` option.

    Args:
        explicit (Optional[int]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[int]: the value for the ``concurrency`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`F2FORMAT_CONCURRENCY` -- the value in environment variable

    See Also:
        :data:`_default_concurrency`

    """
    return parse_positive_integer(explicit or os.getenv('F2FORMAT_CONCURRENCY') or _default_concurrency)


def _get_do_archive_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``do_archive`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``do_archive`` option

    :Environment Variables:
        :envvar:`F2FORMAT_DO_ARCHIVE` -- the value in environment variable

    See Also:
        :data:`_default_do_archive`

    """
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('F2FORMAT_DO_ARCHIVE'))
        yield _default_do_archive
    return first_non_none(_option_layers())


def _get_archive_path_option(explicit: Optional[str] = None) -> str:
    """Get the value for the ``archive_path`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        str: the value for the ``archive_path`` option

    :Environment Variables:
        :envvar:`F2FORMAT_ARCHIVE_PATH` -- the value in environment variable

    See Also:
        :data:`_default_archive_path`

    """
    return explicit or os.getenv('F2FORMAT_ARCHIVE_PATH') or _default_archive_path


def _get_source_version_option(explicit: Optional[str] = None) -> Optional[str]:
    """Get the value for the ``source_version`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        str: the value for the ``source_version`` option

    :Environment Variables:
        :envvar:`F2FORMAT_SOURCE_VERSION` -- the value in environment variable

    See Also:
        :data:`_default_source_version`

    """
    return explicit or os.getenv('F2FORMAT_SOURCE_VERSION') or _default_source_version


def _get_linesep_option(explicit: Optional[str] = None) -> Optional[Linesep]:
    r"""Get the value for the ``linesep`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[Literal['\\n', '\\r\\n', '\\r']]: the value for the ``linesep`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`F2FORMAT_LINESEP` -- the value in environment variable

    See Also:
        :data:`_default_linesep`

    """
    return parse_linesep(explicit or os.getenv('F2FORMAT_LINESEP') or _default_linesep)


def _get_indentation_option(explicit: Optional[Union[str, int]] = None) -> Optional[str]:
    """Get the value for the ``indentation`` option.

    Args:
        explicit (Optional[Union[str, int]]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[str]: the value for the ``indentation`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`F2FORMAT_INDENTATION` -- the value in environment variable

    See Also:
        :data:`_default_indentation`

    """
    return parse_indentation(explicit or os.getenv('F2FORMAT_INDENTATION') or _default_indentation)


def _get_pep8_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``pep8`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``pep8`` option

    :Environment Variables:
        :envvar:`F2FORMAT_PEP8` -- the value in environment variable

    See Also:
        :data:`_default_pep8`

    """
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('F2FORMAT_PEP8'))
        yield _default_pep8
    return first_non_none(_option_layers())


###############################################################################
# Traceback Trimming (tbtrim)

# root path
ROOT = pathlib.Path(__file__).resolve().parent


def predicate(filename: str) -> bool:
    return pathlib.Path(filename).parent == ROOT


tbtrim.set_trim_rule(predicate, strict=True, target=BPCSyntaxError)


###############################################################################
# Main convertion implementation


class Context(BaseContext):
    """General conversion context.

    Args:
        node (parso.tree.NodeOrLeaf): parso AST
        config (Config): conversion configurations

    Keyword Args:
        raw (bool): raw processing flag

    Important:
        ``raw`` should be :data:`True` only if the ``node`` is in the clause of another *context*,
        where the converted wrapper functions should be inserted.

    For the :class:`Context` class of :mod:`f2format` module,
    it will process nodes with following methods:

    * :token:`stringliteral`

      * :meth:`Context._process_strings`
      * :meth:`Context._process_string_context`

    * :token:`f_string`

      * :meth:`Context._process_fstring`

    """

    def _process_strings(self, node: parso.python.tree.PythonNode) -> None:
        """Process concatenable strings (:token:`stringliteral`).

        Args:
            node (parso.python.tree.PythonNode): concatentable strings node

        As in Python, adjacent string literals can be concatenated in certain
        cases, as described in the `documentation`_. Such concatenable strings
        may contain formatted string literals (:term:`f-string`) within its scope.

        _documentation: https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation

        """
        if not self.has_expr(node):
            self += node.get_code()
            return

        # initialise new context
        ctx = StringContext(node, self.config, indent_level=self._indent_level, raw=False)  # type: ignore[arg-type]
        self += ctx.string

    def _process_fstring(self, node: parso.python.tree.PythonNode) -> None:
        """Process formatted strings (:token:`f_string`).

        Args:
            node (parso.python.tree.PythonNode): formatted strings node

        """
        # initialise new context
        ctx = StringContext(node, self.config, indent_level=self._indent_level, raw=False)  # type: ignore[arg-type]
        self += ctx.string

    def _concat(self) -> None:
        """Concatenate final string.

        This method tries to concatenate final result based on the very location
        where starts to contain formatted string literals, i.e. between the converted
        code as :attr:`self._prefix <Context._prefix>` and :attr:`self._suffix <Context._suffix>`.

        """
        # no-op
        self._buffer = self._prefix + self._suffix

    @final
    @classmethod
    def has_expr(cls, node: parso.tree.NodeOrLeaf) -> bool:
        """Check if node has formatted string literals.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has formatted string literals

        """
        if node.type.startswith('fstring'):
            return True

        if hasattr(node, 'children'):
            for child in node.children:  # type: ignore[attr-defined]
                if cls.has_expr(child):
                    return True
        return False

    # backward compatibility and auxiliary alias
    has_f2format = has_expr

    @final
    @classmethod
    def has_debug_fstring(cls, node: parso.tree.NodeOrLeaf) -> bool:
        """Check if node has *debug* formatted string literals.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has debug formatted string literals

        """
        if node.type == 'fstring_expr':
            for expr in node.children:  # type: ignore[attr-defined]
                if expr.type == 'operator' and expr.value == '=':
                    next_sibling = expr.get_next_sibling()
                    if next_sibling.type == 'operator' and next_sibling.value == '}' \
                        or next_sibling.type in ('fstring_conversion', 'fstring_format_spec'):
                        return True
            return False

        if hasattr(node, 'children'):
            for child in node.children:  # type: ignore[attr-defined]
                if cls.has_debug_fstring(child):
                    return True
        return False


class StringContext(Context):
    """String (f-string) conversion context.

    This class is mainly used for converting **formatted string literals**.

    Args:
        node (parso.python.tree.PythonNode): parso AST
        config (Config): conversion configurations

    Keyword Args:
        has_fstring (bool): flag if contains actual formatted
            string literals (with expressions)
        indent_level (int): current indentation level
        raw (bool): raw processing flag

    """
    #: re.Pattern: Pattern matches the formatted string literal prefix (``f``).
    fstring_start = re.compile(r'[fF]', flags=re.ASCII)  # type: Final[ClassVar[re.Pattern]]
    #: re.Pattern: Pattern matches single brackets in the formatted string literal (``{}``).
    fstring_bracket = re.compile(r'([{}])', flags=re.ASCII)  # type: Final[ClassVar[re.Pattern]]

    @final
    @property
    def expr(self) -> List[str]:
        """Expressions extracted from the formatted string literal.

        :rtype: List[str]
        """
        return self._expr

    def __init__(self, node: parso.tree.NodeOrLeaf, config: F2formatConfig, *,
                 has_fstring: Optional[bool] = None, indent_level: int = 0, raw: bool = False):
        if has_fstring is None:
            has_fstring = self.has_fstring(node)

        #: List[str]: Expressions extracted from the formatted string literal.
        self._expr = []  # type: List[str]
        #: bool: Flag if contains actual formatted string literals (with expressions).
        self._flag = has_fstring  # type: bool

        # call super init
        super().__init__(node, config, indent_level=indent_level, raw=raw)

    def _process_fstring(self, node: parso.python.tree.PythonNode) -> None:
        """Process formatted strings (:token:`f_string`).

        Args:
            node (parso.python.tree.PythonNode): formatted strings node

        """
        # initialise new context
        ctx = StringContext(node, self.config, has_fstring=self._flag,  # type: ignore[arg-type]
                            indent_level=self._indent_level, raw=True)
        self += ctx.string
        self._expr.extend(ctx.expr)

    def _process_string(self, node: parso.python.tree.PythonNode) -> None:
        """Process string node (:token:`stringliteral`).

        Args:
            node (parso.python.tree.PythonNode): string node

        """
        if self._flag:
            self += self.fstring_bracket.sub(r'\1\1', node.get_code())
            return

        self += node.get_code()

    def _process_fstring_start(self, node: parso.python.tree.FStringStart) -> None:
        """Process formatted string literal starting node (:token:`stringprefix`).

        Args:
            node (parso.python.tree.FStringStart): formatted literal starting node

        """
        # <FStringStart: ...>
        self += self.fstring_start.sub('', node.get_code())

    def _process_fstring_string(self, node: parso.python.tree.FStringString) -> None:
        """Process formatted string literal string node (:token:`stringliteral`).

        Args:
            node (parso.python.tree.FStringString): formatted string literal string node

        """
        if self._flag:
            self += node.get_code()
            return

        self += node.get_code().replace('{{', '{').replace('}}', '}')

    def _process_fstring_expr(self, node: parso.python.tree.PythonNode) -> None:
        """Process formatted string literal expression node (:token:`f_expression`).

        Args:
            node (parso.python.tree.PythonNode): formatted literal expression node

        """
        # <Operator: {>
        self += node.children[0].get_code().rstrip()

        flag_dbg = False  # is debug f-string?
        conv_str = None  # f-stringconversion
        conv_var = '__f2format_%s' % self._uuid_gen.gen()

        expr_str = ''
        spec_str = ''

        # testlist ['='] [ fstring_conversion ] [ fstring_format_spec ]
        for child in node.children[1:-1]:
            # conversion
            if child.type == 'fstring_conversion':
                conv_str = child.get_code().strip()
                self += conv_str
            # format specification
            elif child.type == 'fstring_format_spec':
                # initialise new context
                ctx = StringContext(child, self.config, has_fstring=None,  # type: ignore[arg-type]
                                    indent_level=self._indent_level, raw=True)
                self += ctx.string.strip()
                spec_str += ''.join(ctx.expr)
            # implicit tuple
            elif child.type == 'testlist':
                expr_str += '(%s)' % child.get_code().strip()
            # embedded f-string
            elif child.type == 'fstring':
                # initialise new context
                ctx = StringContext(child, self.config, has_fstring=None,  # type: ignore[arg-type]
                                    indent_level=self._indent_level, raw=False)
                expr_str += ctx.string
            # concatenable strings
            elif child.type == 'strings':
                # initialise new context
                ctx = StringContext(child, self.config, has_fstring=None,  # type: ignore[arg-type]
                                    indent_level=self._indent_level, raw=False)
                expr_str += ctx.string
            # debug f-string / normal expression
            elif child.type == 'operator' and child.value == '=':
                next_sibling = child.get_next_sibling()
                if (next_sibling.type == 'operator' and next_sibling.value == '}') \
                        or next_sibling.type in ['fstring_conversion', 'fstring_format_spec']:
                    flag_dbg = True
                    expr_tmp = expr_str + child.get_code() + \
                        self.extract_whitespaces(next_sibling.get_code())[0] + \
                        '{%%(%(conv_var)s)s}' % dict(conv_var=conv_var)
                    expr_str = '%r.format(%s)' % (expr_tmp, expr_str)
                else:
                    expr_str += child.get_code()
            # empty format specification
            elif child.type == 'operator' and child.value == ':':
                next_sibling = child.get_next_sibling()
                if (next_sibling.type == 'operator' and next_sibling.value == '}'):
                    self += child.get_code()
                else:
                    expr_str += child.get_code()
            # normal expression
            else:
                expr_str += child.get_code()

        if expr_str:
            if flag_dbg:
                expr_str = expr_str % {conv_var: conv_str or '!r'}
            self._expr.append(expr_str)
        if spec_str:
            self._expr.append(spec_str)

        # <Operator: }>
        self += node.children[-1].get_code().lstrip()

    def _concat(self) -> None:
        """Concatenate final string.

        This method tries to concatenate final result based on the very location
        where starts to contain formatted string literals, i.e. between the converted
        code as :attr:`self._prefix <Context._prefix>` and :attr:`self._suffix <Context._suffix>`.

        """
        if self._expr:
            if self._pep8:
                self._buffer = self._prefix + self._suffix.rstrip() + \
                    '.format(%s)' % ', '.join(map(lambda s: s.strip(), self._expr))
            else:
                self._buffer = self._prefix + self._suffix + '.format(%s)' % ', '.join(self._expr)
            return

        # no-op
        self._buffer = self._prefix + self._suffix

    @final
    @classmethod
    def has_fstring(cls, node: parso.tree.NodeOrLeaf) -> bool:
        """Check if node has actual formatted string literals.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has actual formatted string literals
                (with expressions in the literals)

        """
        if node.type == 'fstring_expr':
            return True

        if hasattr(node, 'children'):
            for child in node.children:  # type: ignore[attr-defined]
                if cls.has_fstring(child):
                    return True
        return False


###############################################################################
# Public Interface


def convert(code: Union[str, bytes], filename: Optional[str] = None, *,
            source_version: Optional[str] = None, linesep: Optional[Linesep] = None,
            indentation: Optional[Union[int, str]] = None, pep8: Optional[bool] = None) -> str:
    """Convert the given Python source code string.

    Args:
        code (Union[str, bytes]): the source code to be converted
        filename (Optional[str]): an optional source file name to provide a context in case of error

    Keyword Args:
        source_version (Optional[str]): parse the code as this Python version (uses the latest version by default)

    :Environment Variables:
     - :envvar:`F2FORMAT_SOURCE_VERSION` -- same as the ``source_version`` argument and the ``--source-version`` option
        in CLI
     - :envvar:`F2FORMAT_LINESEP` -- same as the ``linesep`` argument and the ``--linesep`` option in CLI
     - :envvar:`F2FORMAT_INDENTATION` -- same as the ``indentation`` argument and the ``--indentation`` option in CLI
     - :envvar:`F2FORMAT_PEP8` -- same as the ``pep8`` argument and the ``--no-pep8`` option in CLI (logical negation)

    Returns:
        str: converted source code

    """
    # parse source string
    source_version = _get_source_version_option(source_version)
    module = parso_parse(code, filename=filename, version=source_version)

    # get linesep, indentation and pep8 options
    linesep = _get_linesep_option(linesep)
    indentation = _get_indentation_option(indentation)
    if linesep is None:
        linesep = detect_linesep(code)
    if indentation is None:
        indentation = detect_indentation(code)
    pep8 = _get_pep8_option(pep8)

    # pack conversion configuration
    config = Config(linesep=linesep, indentation=indentation, pep8=pep8,
                    filename=filename, source_version=source_version)

    # convert source string
    result = Context(module, config).string

    # return conversion result
    return result


def f2format(filename: str, *, source_version: Optional[str] = None, linesep: Optional[Linesep] = None,
             indentation: Optional[Union[int, str]] = None, pep8: Optional[bool] = None,
             quiet: Optional[bool] = None, dry_run: bool = False) -> None:
    """Convert the given Python source code file. The file will be overwritten.

    Args:
        filename (str): the file to convert

    Keyword Args:
        source_version (Optional[str]): parse the code as this Python version (uses the latest version by default)
        linesep (Optional[str]): line separator of code (``LF``, ``CRLF``, ``CR``) (auto detect by default)
        indentation (Optional[Union[int, str]]): code indentation style, specify an integer for the number of spaces,
            or ``'t'``/``'tab'`` for tabs (auto detect by default)
        pep8 (Optional[bool]): whether to make code insertion :pep:`8` compliant
        quiet (Optional[bool]): whether to run in quiet mode
        dry_run (bool): if :data:`True`, only print the name of the file to convert but do not perform any conversion

    :Environment Variables:
     - :envvar:`F2FORMAT_SOURCE_VERSION` -- same as the ``source-version`` argument and the ``--source-version`` option
        in CLI
     - :envvar:`F2FORMAT_LINESEP` -- same as the ``linesep`` argument and the ``--linesep`` option in CLI
     - :envvar:`F2FORMAT_INDENTATION` -- same as the ``indentation`` argument and the ``--indentation`` option in CLI
     - :envvar:`F2FORMAT_PEP8` -- same as the ``pep8`` argument and the ``--no-pep8`` option in CLI (logical negation)
     - :envvar:`F2FORMAT_QUIET` -- same as the ``quiet`` argument and the ``--quiet`` option in CLI

    """
    quiet = _get_quiet_option(quiet)
    if not quiet:
        with TaskLock():
            print('Now converting: %r' % filename, file=sys.stderr)
    if dry_run:
        return

    # read file content
    with open(filename, 'rb') as file:
        content = file.read()

    # detect source code encoding
    encoding = detect_encoding(content)

    # get linesep and indentation
    linesep = _get_linesep_option(linesep)
    indentation = _get_indentation_option(indentation)
    if linesep is None or indentation is None:
        with open(filename, 'r', encoding=encoding) as file:
            if linesep is None:
                linesep = detect_linesep(file)
            if indentation is None:
                indentation = detect_indentation(file)

    # do the dirty things
    result = convert(content, filename=filename, source_version=source_version,
                     linesep=linesep, indentation=indentation, pep8=pep8)

    # overwrite the file with conversion result
    with open(filename, 'w', encoding=encoding, newline='') as file:
        file.write(result)


###############################################################################
# CLI & Entry Point

# option values display
# these values are only intended for argparse help messages
# this shows default values by default, environment variables may override them
__cwd__ = os.getcwd()
__f2format_quiet__ = 'quiet mode' if _get_quiet_option() else 'non-quiet mode'
__f2format_concurrency__ = _get_concurrency_option() or 'auto detect'
__f2format_do_archive__ = 'will do archive' if _get_do_archive_option() else 'will not do archive'
__f2format_archive_path__ = os.path.join(__cwd__, _get_archive_path_option())
__f2format_source_version__ = _get_source_version_option()
__f2format_linesep__ = {
    '\n': 'LF',
    '\r\n': 'CRLF',
    '\r': 'CR',
    None: 'auto detect'
}[_get_linesep_option()]
__f2format_indentation__ = _get_indentation_option()
if __f2format_indentation__ is None:
    __f2format_indentation__ = 'auto detect'
elif __f2format_indentation__ == '\t':
    __f2format_indentation__ = 'tab'
else:
    __f2format_indentation__ = '%d spaces' % len(__f2format_indentation__)
__f2format_pep8__ = 'will conform to PEP 8' if _get_pep8_option() else 'will not conform to PEP 8'


def get_parser() -> argparse.ArgumentParser:
    """Generate CLI parser.

    Returns:
        argparse.ArgumentParser: CLI parser for f2format

    """
    parser = argparse.ArgumentParser(prog='f2format',
                                     usage='f2format [options] <Python source files and directories...>',
                                     description='Back-port compiler for Python 3.8 position-only parameters.')
    parser.add_argument('-V', '--version', action='version', version=__version__)
    parser.add_argument('-q', '--quiet', action='store_true', default=None,
                        help='run in quiet mode (current: %s)' % __f2format_quiet__)
    parser.add_argument('-C', '--concurrency', action='store', type=int, metavar='N',
                        help='the number of concurrent processes for conversion (current: %s)' % __f2format_concurrency__)
    parser.add_argument('--dry-run', action='store_true',
                        help='list the files to be converted without actually performing conversion and archiving')
    parser.add_argument('-s', '--simple', action='store', nargs='?', dest='simple_args', const='', metavar='FILE',
                        help='this option tells the program to operate in "simple mode"; '
                             'if a file name is provided, the program will convert the file but print conversion '
                             'result to standard output instead of overwriting the file; '
                             'if no file names are provided, read code for conversion from standard input and print '
                             'conversion result to standard output; '
                             'in "simple mode", no file names shall be provided via positional arguments')

    archive_group = parser.add_argument_group(title='archive options',
                                              description="backup original files in case there're any issues")
    archive_group.add_argument('-na', '--no-archive', action='store_false', dest='do_archive', default=None,
                               help='do not archive original files (current: %s)' % __f2format_do_archive__)
    archive_group.add_argument('-k', '--archive-path', action='store', default=__f2format_archive_path__, metavar='PATH',  # pylint: disable=line-too-long
                               help='path to archive original files (current: %(default)s)')
    archive_group.add_argument('-r', '--recover', action='store', dest='recover_file', metavar='ARCHIVE_FILE',
                               help='recover files from a given archive file')
    archive_group.add_argument('-r2', action='store_true', help='remove the archive file after recovery')
    archive_group.add_argument('-r3', action='store_true', help='remove the archive file after recovery, '
                                                                'and remove the archive directory if it becomes empty')

    convert_group = parser.add_argument_group(title='convert options', description='conversion configuration')
    convert_group.add_argument('-vs', '-vf', '--source-version', '--from-version', action='store', metavar='VERSION',
                               default=__f2format_source_version__, choices=F2FORMAT_SOURCE_VERSIONS,
                               help='parse source code as this Python version (current: %(default)s)')
    convert_group.add_argument('-l', '--linesep', action='store',
                               help='line separator (LF, CRLF, CR) to read '
                                    'source files (current: %s)' % __f2format_linesep__)
    convert_group.add_argument('-t', '--indentation', action='store', metavar='INDENT',
                               help='code indentation style, specify an integer for the number of spaces, '
                                    "or 't'/'tab' for tabs (current: %s)" % __f2format_indentation__)
    convert_group.add_argument('-n8', '--no-pep8', action='store_false', dest='pep8', default=None,
                               help='do not make code insertion PEP 8 compliant (current: %s)' % __f2format_pep8__)

    parser.add_argument('files', action='store', nargs='*', metavar='<Python source files and directories...>',
                        help='Python source files and directories to be converted')

    return parser


def do_f2format(filename: str, **kwargs: object) -> None:
    """Wrapper function to catch exceptions."""
    try:
        f2format(filename, **kwargs)  # type: ignore[arg-type]
    except Exception:  # pylint: disable=broad-except
        with TaskLock():
            print('Failed to convert file: %r' % filename, file=sys.stderr)
            traceback.print_exc()


def main(argv: Optional[List[str]] =None) -> int:
    """Entry point for f2format.

    Args:
        argv (Optional[List[str]]): CLI arguments

    :Environment Variables:
     - :envvar:`F2FORMAT_QUIET` -- same as the ``--quiet`` option in CLI
     - :envvar:`F2FORMAT_CONCURRENCY` -- same as the ``--concurrency`` option in CLI
     - :envvar:`F2FORMAT_DO_ARCHIVE` -- same as the ``--no-archive`` option in CLI (logical negation)
     - :envvar:`F2FORMAT_ARCHIVE_PATH` -- same as the ``--archive-path`` option in CLI
     - :envvar:`F2FORMAT_SOURCE_VERSION` -- same as the ``--source-version`` option in CLI
     - :envvar:`F2FORMAT_LINESEP` -- same as the ``--linesep`` option in CLI
     - :envvar:`F2FORMAT_INDENTATION` -- same as the ``--indentation`` option in CLI
     - :envvar:`F2FORMAT_PEP8` -- same as the ``--no-pep8`` option in CLI (logical negation)

    """
    parser = get_parser()
    args = parser.parse_args(argv)

    options = {
        'source_version': args.source_version,
        'linesep': args.linesep,
        'indentation': args.indentation,
        'pep8': args.pep8,
    }

    # check if running in simple mode
    if args.simple_args is not None:
        if args.files:
            parser.error('no Python source files or directories shall be given as positional arguments in simple mode')
        if not args.simple_args:  # read from stdin
            code = sys.stdin.read()
        else:  # read from file
            filename = args.simple_args
            options['filename'] = filename
            with open(filename, 'rb') as file:
                code = file.read()
        sys.stdout.write(convert(code, **options))  # print conversion result to stdout
        return 0

    # get options
    quiet = _get_quiet_option(args.quiet)
    processes = _get_concurrency_option(args.concurrency)
    do_archive = _get_do_archive_option(args.do_archive)
    archive_path = _get_archive_path_option(args.archive_path)

    # check if doing recovery
    if args.recover_file:
        recover_files(args.recover_file)
        if not args.quiet:
            print('Recovered files from archive: %r' % args.recover_file, file=sys.stderr)
        # TODO: maybe implement deletion in bpc-utils?
        if args.r2 or args.r3:
            os.remove(args.recover_file)
            if args.r3:
                archive_dir = os.path.dirname(os.path.realpath(args.recover_file))
                if not os.listdir(archive_dir):
                    os.rmdir(archive_dir)
        return 0

    # fetch file list
    if not args.files:
        parser.error('no Python source files or directories are given')
    filelist = sorted(detect_files(args.files))

    # terminate if no valid Python source files detected
    if not filelist:
        if not args.quiet:
            # TODO: maybe use parser.error?
            print('Warning: no valid Python source files found in %r' % args.files, file=sys.stderr)
        return 1

    # make archive
    if do_archive and not args.dry_run:
        archive_files(filelist, archive_path)

    # process files
    options.update({
        'quiet': quiet,
        'dry_run': args.dry_run,
    })
    map_tasks(do_f2format, filelist, kwargs=options, processes=processes)

    return 0


if __name__ == '__main__':
    sys.exit(main())
