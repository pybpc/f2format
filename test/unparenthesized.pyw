print(f"{1if'yes'else'no'}")
print(f'{x for x in [1]}'[:17])
print(f'{x for x in [1]} {x for x in [1]}'[:17])
print(f'{x for x in [1]=}'[:32])


def foo(x=0):
    if x == 0:
        print(f"{yield 'end' = }")
        return
    print(f'hello {yield 88} world')
    print(f'yet {(yield "99")} another')
    print(f'{yield from foo()}')


print(list(foo(1)))


async def bar():  # 3.5+
    return f'{await None}'


print(f'{*[1],*[2]}')
print(f'{*(3, 4),*(5, 6)=}')
# TODO: more unpacking for Python 3.5
