import contextlib
import os
import shutil

os.chdir(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

shutil.rmtree('.pytest_cache', ignore_errors=True)
#shutil.rmtree(os.path.join('bpc_template', '__pycache__'), ignore_errors=True)
shutil.rmtree(os.path.join('tests', '__pycache__'), ignore_errors=True)

with contextlib.suppress(OSError):
    os.remove('.coverage')
