# -*- coding: utf-8 -*-

import glob
import locale
import os
import re

import parso

__all__ = ['f2format', 'convert', 'ConvertError']

# from configparser
BOOLEAN_STATES = {'1': True, '0': False,
                  'yes': True, 'no': False,
                  'true': True, 'false': False,
                  'on': True, 'off': False}

# environs
F2FORMAT_QUIET = BOOLEAN_STATES.get(os.getenv('F2FORMAT_QUIET', '0').casefold(), False)
LOCALE_ENCODING = locale.getpreferredencoding(False)

# macros
grammar_regex = re.compile(r"grammar(\d)(\d)\.txt")
F2FORMAT_VERSION = sorted(filter(lambda version: version >= '3.6',  # when Python starts to have f-string
                                 map(lambda path: '%s.%s' % grammar_regex.match(os.path.split(path)[1]).groups(),
                                     glob.glob(os.path.join(parso.__path__[0], 'python', 'grammar??.txt')))))
del grammar_regex


class ConvertError(SyntaxError):
    pass


def convert(string, source='<unknown>'):
    """The main conversion process.

    Args:
     - string -- str, context to be converted
     - source -- str, source of the context

    Envs:
     - F2FORMAT_VERSION -- convert against Python version (same as `--python` option in CLI)

    Returns:
     - str -- converted string

    """
    def parse(string, error_recovery=False):
        try:
            return parso.parse(string, error_recovery=error_recovery,
                               version=os.getenv('F2FORMAT_VERSION', F2FORMAT_VERSION[-1]))
        except parso.ParserSyntaxError as error:
            message = '%s: <%s: %r> from %s' % (error.message, error.error_leaf.token_type,
                                                error.error_leaf.value, source)
            raise ConvertError(message).with_traceback(error.__traceback__)

    def extract(node):
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
                if expr.type == 'fstring_conversion':
                    string += expr.get_code()
                elif expr.type == 'fstring_format_spec':
                    for spec in expr.children:
                        if spec.type != 'fstring_expr':
                            string += spec.get_code()
                            continue

                        # <Operator: {>
                        string += '{'

                        for spec_expr in spec.children[1:-1]:
                            if spec_expr.type == 'fstring_conversion':  # pragma: no cover
                                string += spec_expr.get_code()
                            elif spec_expr.type == 'fstring_format_spec':  # pragma: no cover
                                string += spec_expr.get_code()
                            elif spec_expr.type == 'testlist':  # pragma: no cover
                                spec_str += '(%s)' % spec_expr.get_code()
                            else:
                                spec_str += spec_expr.get_code()

                        # <Operator: }>
                        string += '}'
                elif expr.type == 'testlist':
                    expr_str += '(%s)' % expr.get_code()
                elif expr.type == 'fstring':
                    text, expr = extract(expr)
                    expr_str += text
                    if expr:
                        expr_str += '.format(%s)' % ', '.join(expr)
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
                        expr_str += ''.join(map(lambda text: text[1] if text[0] else re.sub(r'([{}])', r'\1\1', text[1]), text_temp_list))
                        expr_str += '.format(%s)' % ', '.join(expr_temp_list)
                    else:
                        expr_str += ''.join(map(lambda text: text[1], text_temp_list))
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

    # parse source string
    module = parse(string)

    # convert source string
    string = walk(module)

    # return converted string
    return string


def f2format(filename):
    """Wrapper works for conversion.

    Args:
     - filename -- str, file to be converted

    Envs:
     - F2FORMAT_QUIET -- run in quiet mode (same as `--quiet` option in CLI)
     - F2FORMAT_ENCODING -- encoding to open source files (same as `--encoding` option in CLI)
     - F2FORMAT_VERSION -- convert against Python version (same as `--python` option in CLI)

    """
    if not F2FORMAT_QUIET:
        print('Now converting %r...' % filename)

    # fetch encoding
    encoding = os.getenv('F2FORMAT_ENCODING', LOCALE_ENCODING)

    # file content
    with open(filename, 'r', encoding=encoding) as file:
        text = file.read()

    # do the dirty things
    text = convert(text, filename)

    # dump back to the file
    with open(filename, 'w', encoding=encoding) as file:
        file.write(text)
