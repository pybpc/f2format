def _replace(password):
    if password is None:
        return ''
    return (f".replace({password!r}, '********')")


def _ansi2text(password):
    return ('/usr/local/opt/python/bin/python3.7 -c "'
            'import re, sys\n'
            'for line in sys.stdin:\n'
            "    data = line.rstrip().replace('^D\x08\x08', '')\n"
            "    temp = re.sub(r'\x1b\\[[0-9][0-9;]*m', r'', data, flags=re.IGNORECASE)\n"
            f"    text = temp.replace('Password:', 'Password:\\r\\n'){_replace(password)}\n"
            '    if text:\n'
            "        print(text, end='\\r\\n')\n"
            '"')


print(_ansi2text('This is a password.'))
