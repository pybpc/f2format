# -*- coding: utf-8 -*-

import hashlib
import os
import re
import subprocess

import bs4
import requests

with open('./f2format/__main__.py', 'r') as file:
    for line in file:
        match = re.match(r"^__version__ = '(.*)'", line)
        if match is None:
            continue
        VERSION = match.groups()[0]
        break
# print(VERSION)

url = f'https://pypi.org/project/f2format/{VERSION}/#files'
page = requests.get(url)
soup = bs4.BeautifulSoup(page.text, 'html5lib')
table = soup.find_all('table', class_='table--downloads')[0]

for line in filter(lambda item: isinstance(item, bs4.element.Tag), table.tbody):
    item = line.find_all('td')[0]
    link = item.a.get('href') or ''
    if link.endswith('.tar.gz'):
        F2FORMAT_URL = link
        F2FORMAT_SHA = hashlib.sha256(requests.get(F2FORMAT_URL).content).hexdigest()
        break
# print(F2FORMAT_URL)
# print(F2FORMAT_SHA)

PATHLIB2 = subprocess.check_output(['poet', 'pathlib2']).decode().strip()
TYPED_AST = subprocess.check_output(['poet', 'typed_ast']).decode().strip()
# print(PATHLIB2)
# print(TYPED_AST)

FORMULA = f'''\
class F2format < Formula
  include Language::Python::Virtualenv

  desc "Back-port compiler for Python 3.6 f-string literals"
  homepage "https://github.com/JarryShaw/f2format#f2format"
  url "{F2FORMAT_URL}"
  sha256 "{F2FORMAT_SHA}"

  head "https://github.com/JarryShaw/f2format.git", :branch => "master"

  depends_on "python"

  {PATHLIB2}

  {TYPED_AST}

  def install
    # virtualenv_install_with_resources
    venv = virtualenv_create(libexec, "python3")

    version = Language::Python.major_minor_version "python3"
    if version =~ /3.[34]/
      %w[pathlib2 six].each do |r|
        venv.pip_install resource(r)
      end
    end

    if version =~ /3.[345]/
      venv.pip_install resource("typed-ast")
    end
    venv.pip_install_and_link buildpath
  end

  test do
    (testpath/"test.py").write <<~EOS
      var = f'foo{{(1+2)*3:>5}}bar{{"a", "b"!r}}boo'
    EOS

    std_output = <<~EOS
      var = 'foo{{:>5}}bar{{!r}}boo'.format((1+2)*3, ("a", "b"))
    EOS

    system bin/"f2format", "--no-archive", "test.py"
    assert_match std_output, shell_output("cat test.py")
  end
end
'''

with open(os.path.join(os.path.dirname(__file__), 'Tap/Formula/f2format.rb'), 'w') as file:
    file.write(FORMULA)
