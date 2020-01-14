# -*- coding: utf-8 -*-

import contextlib
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

# root path
ROOT = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(ROOT, '..')))
from f2format import ConvertError, convert
from f2format import f2format as core_func
from f2format import get_parser
from f2format import main as main_func
sys.path.pop(0)


class TestF2format(unittest.TestCase):
    def test_get_parser(self):
        parser = get_parser()
        args = parser.parse_args(['-na', '-q', '-p/tmp/',
                                  '-cgb2312', '-v3.6',
                                  'test1.py', 'test2.py'])

        self.assertIs(args.quiet, True,
                      'run in quiet mode')
        self.assertIs(args.archive, False,
                      'do not archive original files')
        self.assertEqual(args.archive_path, '/tmp/',
                         'path to archive original files')
        self.assertEqual(args.encoding, 'gb2312',
                         'encoding to open source files')
        self.assertEqual(args.python, '3.6',
                         'convert against Python version')
        self.assertEqual(args.file, ['test1.py', 'test2.py'],
                         'python source files and folders to be converted')

    def test_main_func(self):
        src_files = glob.glob(os.path.join(os.path.dirname(__file__),
                                           '..', 'test', 'test_?.py'))
        dst_files = list()

        with tempfile.TemporaryDirectory() as tempdir:
            for src in src_files:
                name = os.path.split(src)[1]
                dst = os.path.join(tempdir, name)
                shutil.copy(src, dst)
                dst_files.append(dst)

            # run f2format
            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stderr(devnull):
                    with self.assertRaises(SystemExit):
                        main_func(['-p', os.path.join(tempdir, 'archive'),
                                   'comp', 'docker', 'docs'])
                with contextlib.redirect_stderr(devnull):
                    with self.assertRaises(SystemExit):
                        main_func(['--no-archive', 'comp', 'docker', 'docs'])
                with contextlib.redirect_stdout(devnull):
                    main_func(dst_files)
                with contextlib.redirect_stdout(devnull):
                    temp_args = ['--no-archive', '--quiet']
                    temp_args.extend(dst_files)
                    main_func(temp_args)

            for dst in dst_files:
                src = os.path.join(os.path.dirname(__file__), '..', 'test',
                                   '%s.txt' % pathlib.Path(dst).stem)
                with open(src, 'r') as file:
                    old = file.read()
                new = subprocess.run([sys.executable, dst], stdout=subprocess.PIPE)
                self.assertEqual(old, new.stdout.decode())

    @unittest.skipIf(sys.version_info[:2] < (3, 6),
                     "not supported in this Python version")
    def test_core_func(self):
        def test_core_func_main():
            src_files = glob.glob(os.path.join(os.path.dirname(__file__),
                                               '..', 'test', 'test_?.py'))

            with open(os.devnull, 'w') as devnull:
                with contextlib.redirect_stdout(devnull):
                    with tempfile.TemporaryDirectory() as tempdir:
                        for src in src_files:
                            name = os.path.split(src)[1]
                            dst = os.path.join(tempdir, name)
                            shutil.copy(src, dst)

                            # run f2format
                            core_func(dst)

                            old = subprocess.run([sys.executable, src], stdout=subprocess.PIPE)
                            new = subprocess.run([sys.executable, dst], stdout=subprocess.PIPE)
                            self.assertEqual(old.stdout.decode(), new.stdout.decode())

        os.environ['F2FORMAT_QUIET'] = '1'
        test_core_func_main()

        os.environ['F2FORMAT_QUIET'] = '0'
        test_core_func_main()

        # reset environ
        del os.environ['F2FORMAT_QUIET']

    def test_convert(self):
        # normal convertion
        src = """var = f'foo{(1+2)*3:>5}bar{"a", "b"!r}boo'"""
        dst = convert(src)
        self.assertEqual(dst, """var = 'foo{:>5}bar{!r}boo'.format((1+2)*3, ("a", "b"))""")

        # error convertion
        os.environ['F2FORMAT_VERSION'] = '3.7'
        with self.assertRaises(ConvertError):
            convert("f'a {async} b'")

        # reset environ
        del os.environ['F2FORMAT_VERSION']

    @unittest.skipIf(sys.version_info[:2] < (3, 8),
                     "not supported in this Python version")
    def test_debug_fstring(self):
        # set up environment
        os.environ['F2FORMAT_QUIET'] = '1'
        os.environ['F2FORMAT_VERSION'] = '3.8'

        with tempfile.TemporaryDirectory() as tempdir:
            tmp_file = os.path.join(tempdir, 'temp.py')
            with open(tmp_file, 'w') as file:
                print('b = 1', file=file)
                print("print(f'a {b = :>2} c')")
                print("print(f'a {b = !r:>2} c'")
            old = subprocess.check_output([sys.executable, tmp_file], encoding='utf-8')

            # convert Python 3.8 debug f-string
            core_func(tmp_file)
            new = subprocess.check_output([sys.executable, tmp_file], encoding='utf-8')
            self.assertEqual(old, new)

        # reset environ
        del os.environ['F2FORMAT_QUIET']
        del os.environ['F2FORMAT_VERSION']


if __name__ == '__main__':
    unittest.main()
