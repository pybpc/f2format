# -*- coding: utf-8 -*-


import ast
import copy
import io
import os
import pathlib
import re
import shutil
import sys
import tokenize


# multiprocessing may not be supported
try:        # try first
    import multiprocessing
except ImportError:
    multiprocessing = None
else:       # CPU number if multiprocessing supported
    if os.name == 'posix' and 'SC_NPROCESSORS_CONF' in os.sysconf_names:
        CPU_CNT = os.sysconf('SC_NPROCESSORS_CONF')
    elif 'sched_getaffinity' in os.__all__:
        CPU_CNT = len(os.sched_getaffinity(0))
    else:
        CPU_CNT = os.cpu_count() or 1
finally:    # alias and aftermath
    mp = multiprocessing
    del multiprocessing


# macros
ARCHIVE = 'archive'
HELPMSG = '''\
f2format 0.1.2
usage: f2format [-h] [-n] <python source files and folders..>

Convert f-string to str.format for Python 3 compatibility.

options:
    -h      show this help message and exit
    -n      do not archive original files
'''


def convert(bytestring, lineno):
    """The main conversion process."""
    def find_rbrace(text, quote):
        """Brute force to find right brace."""
        max_offset = len(text)
        offset = 1
        while offset <= max_offset:
            ### print('f%s{%s%s' % (quote, text[:offset], quote))
            try:    # try exclusively
                ast.parse('f%s{%s%s' % (quote, text[:offset], quote))
            except SyntaxError:
                offset += 1
                continue
            ### except Exception as error:
            ###     import traceback
            ###     traceback.print_exc()
            ###     exit(1)
            break
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
            tmpval = module.body[0].value           # either ast.Str or ast.JoinedStr, ast.Module.body[0] -> ast.Expr
            tmpent = list()                         # temporary entry list

            if isinstance(tmpval, ast.JoinedStr):   # ast.JoinedStr is f-string
                rmatch = re.match(r'^((f|rf|fr)(\'\'\'|\'|"""|"))', token.string, re.IGNORECASE)
                prefix = '' if rmatch is None else rmatch.groups()[0]           # fetch string literal prefixes
                quotes = re.sub(r'^rf|fr|f', r'', prefix, flags=re.IGNORECASE)  # quote character(s) for this f-string
                length = len(prefix)                                            # offset from token.string

                for index, obj in enumerate(tmpval.values):     # traverse ast.JoinedStr.values -> list
                    if isinstance(obj, ast.FormattedValue):     # expression part (in braces), ast.FormattedValue
                        start = length + 1                                      # for '{', get start of expression
                        end = start + find_rbrace(token.string[start:], quotes) # find '}', fetch end of expression
                        length += 2 + (end - start)                             # for '{', '}' and expression, update offset
                        if obj.conversion != -1:    end -= 2                    # has conversion ('![rsa]'), minus 2, ast.FormattedValue.converstion -> int
                        if obj.format_spec is not None:                         # has format specification (':...'), minus length of format_spec and colon (':')
                            end -= (len(obj.format_spec.values[0].s) + 1)       # ast.FormattedValue.format_spec -> ast.JoinedStr, .values[0] -> ast.Str
                        tmpent.append(slice(start, end))                        # actual expression slice
                    elif isinstance(obj, ast.Str):              # raw string part, ast.Str, .s -> str
                        raw = token.string[length:]                             # original string
                        end = len(raw)                                          # end of raw string part
                        cnt = 0                                                 # counter for left braces ('{')
                        for i, c in enumerate(raw):                             # enumerate string
                            if c == '{':    cnt += 1                            # increment when reads left brace ('{')
                            elif cnt % 2 == 1:  end = i - 1;    break           # when number of left braces is odd, reach the end
                        length += end
                    else:
                        raise ValueError('malformed node or string:: %r' % obj)
                    ### print('length:', length, '###', token.string[:length], '###', token.string[length:])
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

        ### print()
        ### pprint.pprint(expr)

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


def f2format(filename):
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
    ### print('original:\n', bytestring.decode())
    ### print('###')
    ### print('converted:\n', text.decode())


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

    # check if file is Python source code
    ispy = lambda file: (os.path.isfile(file) and (os.path.splitext(file)[1] in ('.py', '.pyw')))
    filelist = set(filter(ispy, filelist))

    # process files
    if mp is None:
        [ f2format(filename) for filename in filelist ]
    else:
        mp.Pool(processes=CPU_CNT).map(f2format, filelist)


if __name__ == '__main__':
    sys.exit(main())
