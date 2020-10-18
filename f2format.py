# -*- coding: utf-8 -*-
"""Back-port compiler for Python 3.6 f-string literals."""

import argparse
import os
import pathlib
import re
import sys
import traceback

import tbtrim
from bpc_utils import (BaseContext, BPCSyntaxError, Config, TaskLock, archive_files,
                       detect_encoding, detect_files, first_non_none,
                       get_parso_grammar_versions, map_tasks, parse_boolean_state,
                       parse_positive_integer, parso_parse, recover_files)

__all__ = ['main', 'f2format', 'convert']  # pylint: disable=undefined-all-variable

# version string
__version__ = '0.8.6'

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

# option getter utility functions
# option value precedence is: explicit value (CLI/API arguments) > environment variable > default value


def _get_quiet_option(explicit=None):
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
    def _option_layers():
        yield explicit
        yield parse_boolean_state(os.getenv('F2FORMAT_QUIET'))
        yield _default_quiet
    return first_non_none(_option_layers())


def _get_concurrency_option(explicit=None):
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


def _get_do_archive_option(explicit=None):
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
    def _option_layers():
        yield explicit
        yield parse_boolean_state(os.getenv('F2FORMAT_DO_ARCHIVE'))
        yield _default_do_archive
    return first_non_none(_option_layers())


def _get_archive_path_option(explicit=None):
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


def _get_source_version_option(explicit=None):
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


###############################################################################
# Traceback Trimming (tbtrim)

# root path
ROOT = pathlib.Path(__file__).resolve().parent


def predicate(filename):
    return pathlib.Path(filename).parent == ROOT


tbtrim.set_trim_rule(predicate, strict=True, target=BPCSyntaxError)

###############################################################################
# Obsoleted code


def extract(node):
    """Extract f-string components.

    Args:
     - `node` -- `parso.python.tree.PythonNode`, parso AST for f-string

    Returns:
     - `str` -- extracted f-string string components
     - `List[str]` -- extracted f-string expressions

    """
    # FStringStart
    string = re.sub(r'[fF]', '', node.children[0].get_code())

    expr_list = list()
    for child in node.children[1:-1]:
        if child.type != 'fstring_expr':
            string += child.get_code()
            continue

        # <Operator: {>
        string += '{'

        expr_str = ''
        spec_str = ''
        for expr in child.children[1:-1]:
            # conversion
            if expr.type == 'fstring_conversion':
                string += expr.get_code().strip()
            # format specification
            elif expr.type == 'fstring_format_spec':
                for spec in expr.children:
                    if spec.type != 'fstring_expr':
                        string += spec.get_code().strip()
                        continue

                    # <Operator: {>
                    string += '{'

                    for spec_expr in spec.children[1:-1]:
                        if spec_expr.type == 'fstring_conversion':  # pragma: no cover
                            string += spec_expr.get_code().strip()
                        elif spec_expr.type == 'fstring_format_spec':  # pragma: no cover
                            string += spec_expr.get_code().strip()
                        elif spec_expr.type == 'testlist':  # pragma: no cover
                            spec_str += '(%s)' % spec_expr.get_code()
                        else:
                            spec_str += spec_expr.get_code()

                    # <Operator: }>
                    string += '}'
            # implicit tuple
            elif expr.type == 'testlist':
                expr_str += '(%s)' % expr.get_code()
            # embedded f-string
            elif expr.type == 'fstring':
                text, expr = extract(expr)
                expr_str += text
                if expr:
                    expr_str += '.format(%s)' % ', '.join(expr)
            # concatenable strings
            elif expr.type == 'strings':
                text_temp_list = list()
                expr_temp_list = list()
                for expr_child in expr.children:
                    if expr_child.type == 'fstring':
                        text_temp, expr_temp = extract(expr_child)
                        text_temp_list.append((True, text_temp))
                        expr_temp_list.extend(expr_temp)
                    else:
                        text_temp_list.append((False, expr_child.get_code()))
                if expr_temp_list:
                    expr_str += ''.join(map(lambda text: text[1] if text[0]
                                            else re.sub(r'([{}])', r'\1\1', text[1]), text_temp_list))
                    expr_str += '.format(%s)' % ', '.join(expr_temp_list)
                else:
                    expr_str += ''.join(map(lambda text: text[1], text_temp_list))
            # regular expression / debug f-string
            elif expr.type == 'operator' and expr.value == '=':
                next_sibling = expr.get_next_sibling()
                if (next_sibling.type == 'operator' and next_sibling.value == '}') \
                    or next_sibling.type in ['fstring_conversion', 'fstring_format_spec']:
                    expr_tmp = expr_str + expr.get_code() + re.sub(r'\S+.*$', r'', next_sibling.get_code()) + '{}'
                    expr_str = '%r.format(%s)' % (expr_tmp, expr_str)
                else:  # pragma: no cover
                    expr_str += expr.get_code()
            # regular expression
            else:
                expr_str += expr.get_code()

        if expr_str:  # pragma: no cover
            expr_list.append(expr_str)
        if spec_str:
            expr_list.append(spec_str)

        # <Operator: }>
        string += '}'

    # FStringEnd
    string += node.children[-1].get_code()

    return string, expr_list


def walk(node):
    """Walk parso AST.

    Args:
     - `node` -- `parso.python.tree.Module`, parso AST

    Returns:
     - `str` -- converted string

    """
    string = ''

    if node.type == 'strings':
        text_list = list()
        expr_list = list()
        for child in node.children:
            if child.type == 'fstring':
                text, expr = extract(child)
                text_list.append((True, text))
                expr_list.extend(expr)
            else:
                text_list.append((False, child.get_code()))
        if expr_list:
            string += ''.join(map(lambda text: text[1] if text[0] else re.sub(r'([{}])', r'\1\1', text[1]), text_list))
            string += '.format(%s)' % ', '.join(expr_list)
        else:
            string += ''.join(map(lambda text: text[1], text_list))
        return string

    if node.type == 'fstring':
        text, expr = extract(node)
        string += text
        if expr:
            string += '.format(%s)' % ', '.join(expr)
        return string

    if isinstance(node, parso.python.tree.PythonLeaf):
        string += node.get_code()

    if hasattr(node, 'children'):
        for child in node.children:
            string += walk(child)

    return string


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

        However, this parameter is currently not in use.

    For the :class:`Context` class of :mod:`f2format` module,
    it will process nodes with following methods:

    * :token:`stringliteral`

      * :meth:`Context._process_strings`
      * :meth:`Context._process_string_context`

    * :token:`f_string`

      * :meth:`Context._process_fstring`

    """

    def _process_strings(self, node):
        """Process concatenable strings (:token:`stringliteral`).

        Args:
            node (parso.python.tree.PythonNode): concatentable strings node

        As in Python, adjacent string literals can be concatenated in certain
        cases, as described in the `documentation`_. Such concatenable strings
        may contain formatted string literals (:term:`f-string`) within its scope.

        _documentation: https://docs.python.org/3/reference/lexical_analysis.html#string-literal-concatenation

        """

    def _process_fstring(self, node):
        """Process formatted strings (:token:`f_string`).

        Args:
            node (parso.python.tree.PythonNode): formatted strings node

        """

    def _concat(self):
        """Concatenate final string.

        This method tries to concatenate final result based on the very location
        where starts to contain formatted string literals, i.e. between the converted
        code as :attr:`self._prefix <Context._prefix>` and :attr:`self._suffix <Context._suffix>`.

        """
        # no-op
        self._buffer = self._prefix + self._suffix

    @staticmethod
    def has_expr(node):
        """Check if node has formatted string literals.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has formatted string literals

        """

    # backward compatibility and auxiliary alias
    has_f2format = has_expr
    has_fstring = has_expr

    @staticmethod
    def has_debug_fstring(node):
        """Check if node has *debug* formatted string literals.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has debug formatted string literals

        """


def convert(code, filename=None, *, source_version=None):
    """Convert the given Python source code string.

    Args:
        code (Union[str, bytes]): the source code to be converted
        filename (Optional[str]): an optional source file name to provide a context in case of error

    Keyword Args:
        source_version (Optional[str]): parse the code as this Python version (uses the latest version by default)

    :Environment Variables:
     - :envvar:`F2FORMAT_SOURCE_VERSION` -- same as the ``source_version`` argument and the ``--source-version`` option
        in CLI

    Returns:
        str: converted source code

    """
    # parse source string
    source_version = _get_source_version_option(source_version)
    module = parso_parse(code, filename=filename, version=source_version)

    # pack conversion configuration
    config = Config(filename=filename, source_version=source_version)

    # convert source string
    result = Context(module, config).string

    # return conversion result
    return result


def f2format(filename, *, source_version=None, quiet=None, dry_run=False):
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

    # do the dirty things
    result = convert(content, filename=filename, source_version=source_version)

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


def get_parser():
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
    archive_group.add_argument('-k', '--archive-path', action='store', default=__f2format_archive_path__, metavar='PATH',
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

    parser.add_argument('files', action='store', nargs='*', metavar='<Python source files and directories...>',
                        help='Python source files and directories to be converted')

    return parser


def do_f2format(filename, **kwargs):
    """Wrapper function to catch exceptions."""
    try:
        f2format(filename, **kwargs)
    except Exception:  # pylint: disable=broad-except
        with TaskLock():
            print('Failed to convert file: %r' % filename, file=sys.stderr)
            traceback.print_exc()


def main(argv=None):
    """Entry point for f2format.

    Args:
        argv (Optional[List[str]]): CLI arguments

    :Environment Variables:
     - :envvar:`F2FORMAT_QUIET` -- same as the ``--quiet`` option in CLI
     - :envvar:`F2FORMAT_CONCURRENCY` -- same as the ``--concurrency`` option in CLI
     - :envvar:`F2FORMAT_DO_ARCHIVE` -- same as the ``--no-archive`` option in CLI (logical negation)
     - :envvar:`F2FORMAT_ARCHIVE_PATH` -- same as the ``--archive-path`` option in CLI
     - :envvar:`F2FORMAT_SOURCE_VERSION` -- same as the ``--source-version`` option in CLI

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
        return

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
        return

    # fetch file list
    if not args.files:
        parser.error('no Python source files or directories are given')
    filelist = sorted(detect_files(args.files))

    # terminate if no valid Python source files detected
    if not filelist:
        if not args.quiet:
            # TODO: maybe use parser.error?
            print('Warning: no valid Python source files found in %r' % args.files, file=sys.stderr)
        return

    # make archive
    if do_archive and not args.dry_run:
        archive_files(filelist, archive_path)

    # process files
    options.update({
        'quiet': quiet,
        'dry_run': args.dry_run,
    })
    map_tasks(do_f2format, filelist, kwargs=options, processes=processes)


if __name__ == '__main__':
    sys.exit(main())
