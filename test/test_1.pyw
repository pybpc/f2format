v1 = 123
v2 = 'looooo'
v3 = 10

s1 = (f'vv:\377vv{v1}ww!{{}}ww{v2!r}\\xxx\x03{v2+"!"!s}{v2+"""}"""!a}{{llooo}}{{{v2+":":>10}\''
      r'''yaaa\n'aa'''
      "wawa{nono}wa{{}}wa\\"
      RF"""xi'''{v2+'''w'''}xi{v2+'!'}k\k"""'kuux' + 'padding!')
print(ascii(s1))

s2 = "f'fake{f}string!'"
print(s2)

s3 = f'yet_another_{s1,v2!r:<5}_fstring!:'.replace('another', 'other')
print(ascii(s3))

s4 = f'{v2}'
print(s4)

s5 = f'''multiline
\
fstring - {v1} -> {v2:>{v3}}
'''
print(s5)
