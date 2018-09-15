# -*- coding: utf-8 -*-


import ast
import contextlib
import copy
import io
import multiprocessing
import os
import pathlib
import re
import shutil
import sys
import tokenize


# CPU number
if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:
    CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')
elif 'sched_getaffinity' in os.__all__:
    CPU_CNT = len(os.sched_getaffinity(0))
else:
    CPU_CNT = os.cpu_count() or 1


# macros
ARCHIVE = 'archive'
HELPMSG = '''\
f2format 0.1.1
usage: f2format [-h] [-n] <python source files and folders..>

Convert f-string to str.format for Python 3 compatibility.

options:
    -h      show this help message and exit
    -n      do not archive original files
'''


def convert(bytestring, lineno):
    def find_rbrace(text, quote):
        """Brute force to find right brace."""
        max_offset = len(text)
        offset = 1
        while offset <= max_offset:
            ### print('f%s{%s%s' % (quote, text[:offset], quote))
            try:    # try exclusively
                with contextlib.suppress(SyntaxError):
                    eval('f%s{%s%s' % (quote, text[:offset], quote))
            except Exception:
                ### import traceback
                ### traceback.print_exc()
                ### print()
                break
            offset += 1
        return (offset - 1)

    source = bytearray(bytestring)  # bytearray source (mutable)
    string = bytestring.decode()    # string for tokenisation

    f_string = [list()] # [[token, ...], [...], ...] -> concatenable strings

    str_flag = False    # if previous item is token.STRING
    for token in tokenize.generate_tokens(io.StringIO(string).readline):
        cat_flag = False                # if item is concatenable with previous item, i.e. adjacent string
        if token.type == tokenize.STRING:
            if str_flag:    cat_flag = True
            if cat_flag:    f_string[-1].append(token)
            else:           f_string.append([token])
            str_flag = True
        elif token.type == tokenize.NL: # skip token.NL
            continue
        else:                           # otherwise, not concatenable
            str_flag = False
        ### print(token)

    ### print()

    ### import pprint
    ### pprint.pprint(f_string)

    ### print()

    text = copy.deepcopy(source)        # make a copy, just in case
    for tokens in reversed(f_string):   # for each string concatenation
        # check if has f-string literal in this concatenation
        py36 = any(map(lambda token: re.match(r'^(f|rf|fr)', token.string, re.IGNORECASE), tokens))
        if not py36:    continue

        entryl = list()
        for token in tokens:
            module = ast.parse(token.string)        # parse AST, get ast.Module, ast.Module.body -> list
            tmpval = module.body[0].value           # either ast.Str or ast.JoinedStr
            tmpent = list()                         # temporary entry list

            if isinstance(tmpval, ast.JoinedStr):   # ast.JoinedStr is f-string
                rmatch = re.match(r'^((f|rf|fr)(\'\'\'|\'|"""|"))', token.string, re.IGNORECASE)
                prefix = '' if rmatch is None else rmatch.groups()[0]           # fetch string literal prefixes
                quotes = re.sub(r'^rf|fr|f', r'', prefix, flags=re.IGNORECASE)  # quote character(s) for this f-string
                length = len(prefix)                                            # offset from token.string

                for obj in tmpval.values:           # traverse ast.JoinedStr.values -> list
                    if isinstance(obj, ast.FormattedValue):     # expression part (in braces)
                        start = length + 1                                      # for '{', get start of expression
                        end = start + find_rbrace(token.string[start:], quotes) # find '}', fetch end of expression
                        length += 2 + (end - start)                             # for '{', '}' and expression, update offset
                        if obj.conversion != -1:    end -= 2                    # has conversion ('![rsa]'), minus 2
                        if obj.format_spec is not None:                         # has format specification (':...')
                            end -= (len(obj.format_spec.values[0].s) + 1)       # minus length of format_spec and colon (':')
                        tmpent.append(slice(start, end))                        # actual expression slice
                    else:                                       # raw string part
                        length += len(obj.s) + obj.s.count('{') + obj.s.count('}')
                                                                # ast.Str.s -> str, count '{}' twice for escape sequence
                    ### print(length)
            entryl.append((token, tmpent))          # each token with a concatenation entry list

        ### pprint.pprint(entryl)
        ### print()

        expr = list()
        for token, entries in entryl:     # extract expressions
            ### print(token.string, entries)
            expr.extend(token.string[entry].encode() for entry in entries)

        # convert end of f-string to str.format literal, right bracket ')' for compabitlity in multi-lines
        end = lineno[tokens[-1].end[0]] + tokens[-1].end[1]
        text[end:end+1] = b').format(%s)%s' % (b'%s%s%s' % (b'(', b'), ('.join(expr), b')'), chr(text[end]).encode())

        ### print(expr)

        # for each token, convert expression literals and brace '{}' escape sequences
        for token, entries in reversed(entryl):     # using reversed to keep offset in leading context
            token_start = lineno[token.start[0]] + token.start[1]   # actual offset at start of token
            token_end = lineno[token.end[0]] + token.end[1]         # actual offset at end of token
            if entries:     # for f-string expressions, replace with empty string ('')
                for entry in reversed(entries):
                    start = token_start + entry.start
                    end = token_start + entry.stop
                    text[start:end] = b''
            else:           # for escape sequences, double braces
                text[token_start:token_end] = re.sub(rb'([{}])', rb'\1\1', text[token_start:token_end])

            # strip leading f-string literals ('[fF]')
            text[token_start:token_start+3] = re.sub(rb'[fF]', rb'', text[token_start:token_start+3])

        # then add left bracket '(' for compabitlity in multi-lines
        start = lineno[tokens[0].start[0]] + tokens[0].start[1]
        text[start:start+1] = b'(%s' % text[start:start+1]

    # return modified context
    return text


def prepare(filename):
    """Wrapper works for conversion."""
    print(f'Now converting {filename!r}...')

    lineno = dict()     # line number -> file offset
    content = list()    # file content
    with open(filename, 'rb') as file:
        lineno[1] = file.tell()
        for lnum, line in enumerate(file):
            lineno[lnum+2] = file.tell()
            content.append(line)

    # now, do the dirty works
    bytestring = b''.join(content)
    text = convert(bytestring, lineno)

    # dump back to the file
    with open(filename, 'wb') as file:
        file.write(text)

    ### print()
    ### print('original:', repr(bytestring.decode()))
    ### print('converted:', repr(text.decode()))


def main():
    """Entry point for f2format."""
    def find(root):
        """Recursively find all files under root."""
        flst = list()
        temp = os.listdir(root)
        for file in temp:
            path = os.path.join(root, file)
            if os.path.isdir(path):     flst.extend(find(path))
            elif os.path.isfile(path):  flst.append(path)
            elif os.path.islink(path):  continue    # exclude symbolic links
        yield from flst

    def ispy(file):
        """Check if file is Python source code."""
        return (os.path.isfile(file) and (os.path.splitext(file)[1] in ('.py', '.pyw')))

    # help command
    if '-h' in sys.argv[1:]:
        print(HELPMSG)
        return

    # do not make archive
    archive = True
    if '-n' in sys.argv[1:]:
        archive = False

    # make archive directory
    if archive:
        pathlib.Path(ARCHIVE).mkdir(parents=True, exist_ok=True)

    # fetch file list
    filelist = list()
    for path in sys.argv[1:]:
        if os.path.isfile(path):
            if archive:
                shutil.copy(path, os.path.join(ARCHIVE, path.replace(os.path.sep, '_')))
            filelist.append(path)
        if os.path.isdir(path):
            if archive:
                shutil.copytree(path, os.path.join(ARCHIVE, path))
            filelist.extend(find(path))
    filelist = set(filter(ispy, filelist))

    # process files
    multiprocessing.Pool(processes=CPU_CNT).map(prepare, filelist)


if __name__ == '__main__':
    sys.exit(main())
