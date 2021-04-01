print(f"L1 -> {chr(77)!r} <- L1")
print(f'L1 -> {f"L2 -> {chr(77)!r} <- L2"} <- L1')
print(f"""L1 -> {f'L2 -> {f"L3 -> {chr(77)!r} <- L3"} <- L2'} <- L1""")

print(f'''L1 -> {f"""L2 -> {f'L3 -> {f"L4 -> {chr(77)!r} <- L4"} <- L3'} <- L2"""} <- L1''')
print(f'''L1 -> {f"""L2 -> {f'L3 -> {f"L4 -> {chr(77)!r} <- L4"} <- L3'} <- L2"""} <- L1''')
