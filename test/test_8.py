print(f'1')
print(f'escape{{brackets}}')
print(f'{"u"!r}')
print(f'{"v"!s}')
print(f'{"w"!a}')
print(f'{"x":}i')
print(f'{"y":10}2')
print(f'3{chr(20320)+chr(22909)!a:}4')
print(f'5{"z"!s:10}6')
print(f'{666,777=}')  # TODO: more unpacking for Python 3.5
print(f'{"c"+"d" = }')
print(f'{"e"=!r}')
print(f'{"f"=!s}')
print(f"{'g'+'u'=!a}")
print(f'{"h"=:}l')
print(f'{"i"=:10}o')
print(f'7{chr(20013) + chr(25991) = !a:}8')
print(f'{{9{"k"=!s:10}10}}')
print(RF'''prefix\n
{'h' + 'e':{2+3}}middle{6==7=}
suffix''')
# TODO: more complicated nested replacement field


def foo():
    print(f'hello {yield 88} world')


print(list(foo()))

# TODO: need more review of grammar, also need invalid cases
