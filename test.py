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

from f2format.__main__ import get_parser
from f2format.__main__ import main as main_func
from f2format.core import ConvertError, convert
from f2format.core import f2format as core_func


class TestF2format(unittest.TestCase):

    def test_get_parser(self):
        parser = get_parser()
        args = parser.parse_args(['-n', '-q', '-p/tmp/',
                                  '-cgb2312', '-v3.6',
                                  'test1.py', 'test2.py'])

        self.assertIs(args.quiet, True,
                      'run in quiet mode')
        self.assertIs(args.no_archive, True,
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
                                           'test', 'test_?.py'))
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
                        main_func(['comp', 'docker', 'docs'])
                with contextlib.redirect_stdout(devnull):
                    main_func(dst_files)

            for dst in dst_files:
                src = os.path.join(os.path.dirname(__file__), 'test',
                                   '%s.txt' % pathlib.Path(dst).stem)
                with open(src, 'r') as file:
                    old = file.read()
                new = subprocess.run([sys.executable, dst], stdout=subprocess.PIPE)
                self.assertEqual(old, new.stdout.decode())

    @unittest.skipIf(sys.version_info[:2] < (3, 6),
                     "not supported in this Python version")
    def test_core_func(self):
        src_files = glob.glob(os.path.join(os.path.dirname(__file__),
                                           'test', 'test_?.py'))

        os.environ['F2FORMAT_QUIET'] = '1'
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
            convert("""var = f'foo{{(1+2)*3:>5}bar{"a", "b"!r}boo'""")

        # reset environ
        del os.environ['F2FORMAT_VERSION']

if __name__ == '__main__':
    unittest.main()
