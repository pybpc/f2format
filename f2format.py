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


# help message
HELP = """\
f2format 0.1.0
usage: f2format <python source files and folders..>
"""


def find_rbrace(text):
    offset = 1
    while True:
        ### print('f"{%s' % text[:offset])
        try:
            with contextlib.suppress(SyntaxError):
                eval('f"{%s"' % text[:offset])
        except Exception:
            ### import traceback
            ### traceback.print_exc()
            ### print()
            break
        offset += 1
    return (offset - 1)


def convert(bytestring, lineno):
    source = bytearray(bytestring)
    string = bytestring.decode()

    f_string = [list()] # [[token, ...], [...], ...] -> concatenable strings

    str_flag = False
    for token in tokenize.generate_tokens(io.StringIO(string).readline):
        cat_flag = False
        if token.type == tokenize.STRING:
            if str_flag:    cat_flag = True
            if cat_flag:
                f_string[-1].append(token)
            else:
                f_string.append([token])
            str_flag = True
        else:
            str_flag = False
        ### print(token)

    ### print()

    ### import pprint
    ### pprint.pprint(f_string)

    ### print()

    text = copy.deepcopy(source)
    for tokens in reversed(f_string):
        py36 = any(map(lambda token: re.match(r'^(f|rf|fr)', token.string, re.IGNORECASE), tokens))
        if not py36:
            continue

        entryl = list()
        for token in tokens:
            rmatch = re.match(r'^((f|rf|fr)(\'\'\'|\'|"""|"))', token.string, re.IGNORECASE)
            prefix = '' if rmatch is None else rmatch.groups()[0]
            tmpent = list()
            module = ast.parse(token.string)
            tmpval = module.body[0].value
            length = len(prefix)
            if isinstance(tmpval, ast.JoinedStr):
                for obj in tmpval.values:
                    if isinstance(obj, ast.FormattedValue):
                        start = length + 1
                        end = start + find_rbrace(token.string[start:])
                        length += 2 + (end - start)
                        if obj.conversion != -1:    end -= 2
                        if obj.format_spec is not None:
                            end -= (len(obj.format_spec.values[0].s) + 1)
                        tmpent.append(slice(start, end))
                    else:
                        length += len(obj.s)
                    ### print(length)
            entryl.append((token, tmpent))

        ### pprint.pprint(entryl)
        ### print()

        expr = list()
        for token, entries in reversed(entryl):
            ### print(token.string, entries)
            expr.extend(token.string[entry].encode() for entry in reversed(entries))

        end = lineno[tokens[-1].end[0]] + tokens[-1].end[1]
        text[end:end+1] = b').format(%s)%s' % (b', '.join(reversed(expr)), chr(text[end]).encode())

        for token, entries in reversed(entryl):
            token_start = lineno[token.start[0]] + token.start[1]
            token_end = lineno[token.end[0]] + token.end[1]
            if entries:
                for entry in reversed(entries):
                    start = token_start + entry.start
                    end = token_start + entry.stop
                    text[start:end] = b''
            else:
                text[token_start:token_end] = re.sub(rb'([{}])', rb'\1\1', text[token_start:token_end])

            text[token_start:token_start+3] = re.sub(rb'[fF]', rb'', text[token_start:token_start+3])

        start = lineno[tokens[0].start[0]] + tokens[0].start[1]
        text[start:start+1] = b'(%s' % text[start:start+1]

    return text


def prepare(filename):
    print(f'Now converting {filename!r}...')
    shutil.move(file, f'archive/{file.replace(os.path.sep, '_')}')

    lineno = dict()
    context = list()
    with open(filename, 'rb') as file:
        lineno[1] = file.tell()
        for lnum, line in enumerate(file):
            lineno[lnum+2] = file.tell()
            context.append(line)

    bytestring = b''.join(context)
    text = convert(bytestring, lineno)

    with open(filename, 'wb') as file:
        file.write(text)

    ### print()
    ### print('original:', repr(bytestring.decode()))
    ### print('converted:', repr(text.decode()))


def main():
    def ispy(file):
        return (os.path.isfile(file) and (file.endswith('py') or file.endswith('pyw')))

    filelist = list()
    for path in sys.argv[1:]:
        if path in ('-h', '--help'):
            print(HELP)
        if os.path.isfile(path):
            filelist.append(path)
        if os.path.isdir(path):
            filelist.extend(filter(ispy, os.listdir(path)))
    filelist = set(filelist)

    pathlib.Path('archive').mkdir(parents=True, exist_ok=True)
    multiprocessing.Pool(processes=CPU_CNT).map(prepare, filelist)


if __name__ == '__main__':
    sys.exit(main())
