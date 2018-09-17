v1 = 123
v2 = 'looooo'

s1 = ('vv:\377vv{}ww!{{}}ww{!r}\\xxx\x03{!s}{!a}{{llooo}}{{{:>10}\''
      r'''yaaa\n'aa''' \
      "wawa{{nono}}wa{{{{}}}}wa\\"
      R"""xi'''{}xi{}k\k"""'kuux'.format(v1, v2, v2+"!", v2+"""}""", v2+":", v2+'''w''', v2+'!') + 'padding!')
print(s1)

s2 = "f'fake{f}string!'"
print(s2)

s3 = 'yet_another_{!r:<5}_fstring!:'.format((s1,v2)).replace('another', 'other')
print(s3)
