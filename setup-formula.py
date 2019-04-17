# -*- coding: utf-8 -*-

import hashlib
import os
import re
import subprocess

import requests

with open('./f2format/__main__.py', 'r') as file:
    for line in file:
        match = re.match(r"^__version__ = '(.*)'", line)
        if match is None:
            continue
        VERSION = match.groups()[0]
        break
# print(VERSION)

F2FORMAT_URL = f'https://github.com/JarryShaw/f2format/archive/v{VERSION}.tar.gz'
F2FORMAT_SHA = hashlib.sha256(requests.get(F2FORMAT_URL).content).hexdigest()
# print(F2FORMAT_URL)
# print(F2FORMAT_SHA)

PARSO = subprocess.check_output(['poet', 'parso']).decode().strip()
TBTRIM = subprocess.check_output(['poet', 'tbtrim']).decode().strip()
# print(PARSO)
# print(TBTRIM)

FORMULA = f'''\
class F2format < Formula
  include Language::Python::Virtualenv

  desc "Back-port compiler for Python 3.6 f-string literals"
  homepage "https://github.com/JarryShaw/f2format#f2format"
  url "{F2FORMAT_URL}"
  sha256 "{F2FORMAT_SHA}"

  head "https://github.com/JarryShaw/f2format.git", :branch => "master"

  depends_on "python"

  {PARSO}

  {TBTRIM}

  def install
    virtualenv_install_with_resources
    man1.install "man/f2format.1"
    bash_completion.install "comp/f2format.bash-completion"
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
