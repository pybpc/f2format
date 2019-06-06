v1 = 'foo'
v2 = 'bar'
v3 = 10

s1 = '{a}' 'fake' '{{fstring}}'
print(s1)

s2 = '{a}' f'fake' '{{fstring}}'
print(s2)

s3 = f"a {v1,v2!r:>{v3}} real {'{a}' 'fake' '{{fstring}}'} fstring"
print(s3)

s4 = f"a {v1,v2!r:>{v3}} real {'{a}' f'fake' '{{fstring}}'} fstring"
print(s4)

s5 = f'a {f"a {v1} real {v2} fstring"} real {f"a fake fstring"} fstring'
print(s5)
