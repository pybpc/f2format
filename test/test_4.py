import getpass
import time

text = f'''\
Today is {time.ctime(time.time())}
My name is {getpass.getuser()}
'''

print(text)
