# -*- coding: utf-8 -*-

import hashlib
import os
import re
import subprocess

import bs4
import requests

with open('./f2format.py', 'r') as file:
    for line in file:
        match = re.match(r'f2format (.*)', line)
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

DEVEL_URL = f'https://codeload.github.com/JarryShaw/f2format/tar.gz/v{VERSION}'
DEVEL_SHA = hashlib.sha256(requests.get(DEVEL_URL).content).hexdigest()
# print(DEVEL_URL)
# print(DEVEL_SHA)

PATHLIB2 = subprocess.check_output(['poet', 'pathlib2']).decode().strip()
TYPED_AST = subprocess.check_output(['poet', 'typed_ast']).decode().strip()
# print(PATHLIB2)
# print(TYPED_AST)

FORMULA = f'''\
class Macdaily < Formula
  include Language::Python::Virtualenv

  version "{VERSION}"
  desc "Back-port compiler for Python 3.6 f-string literals."
  homepage "https://github.com/JarryShaw/f2format#f2format"
  url "{F2FORMAT_URL}"
  sha256 "{F2FORMAT_SHA}"
  head "https://github.com/JarryShaw/f2format.git", :branch => "master"

  bottle :unneeded

  devel do
    url "{DEVEL_URL}"
    sha256 "{DEVEL_SHA}"
  end

  depends_on "python"

  {PATHLIB2}

  {TYPED_AST}

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"f2format", "--help"
  end
end
'''

with open(os.path.join(os.path.dirname(__file__), 'Tap/Formula/f2format.rb'), 'w') as file:
    file.write(FORMULA)
