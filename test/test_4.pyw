import getpass
import time

text = f'''\
Today is {time.ctime(1556979914.749266)}
My name is {getpass.getuser()}
'''

print(text)
