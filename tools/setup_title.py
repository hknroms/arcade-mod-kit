"""ひな形の {{…}} を title.json の値で埋める（新しいタイトルのリポジトリで1回だけ）。
usage: python3 tools/setup_title.py           （title.json を先に埋めておく）
       python3 tools/setup_title.py --check   （埋め残しを表示するだけ）
"""
import os, re, sys, json
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
t = json.load(open(os.path.join(HERE, 'title.json'), encoding='utf-8'))
owner, name = t['repo'].split('/', 1)
V = {
    'TITLE': t['title'], 'REPO': t['repo'], 'OWNER': owner, 'REPO_NAME': name,
    'DRIVER': t['mame']['driver'], 'SUBTARGET': t['mame']['subtarget'],
    'PAGES': t['pages'], 'PAGES_HOST': t['pages'].replace('https://', '').rstrip('/'),
}
bad = [k for k, v in V.items() if '（' in v or not v]
if bad and '--check' not in sys.argv:
    sys.exit('title.json がまだ埋まっていません: ' + ', '.join(bad))
SKIP = {'.git', 'docs/knowhow', 'tools/setup_title.py', 'SETUP.md'}
pat = re.compile(r'\{\{(' + '|'.join(V) + r')\}\}')
left = []
for root, dirs, files in os.walk(HERE):
    rel = os.path.relpath(root, HERE)
    dirs[:] = [d for d in dirs if os.path.normpath(os.path.join(rel, d)) not in SKIP]
    for f in files:
        p = os.path.join(root, f); r = os.path.normpath(os.path.relpath(p, HERE))
        if r in SKIP or not f.endswith(('.md', '.html', '.yml', '.json', '.js', '.sh', '.lua', '.py', '.txt')): continue
        s = open(p, encoding='utf-8').read()
        if '--check' in sys.argv:
            left += [f'{r}: {m}' for m in sorted(set(pat.findall(s)))]
            continue
        n = pat.sub(lambda m: V[m.group(1)], s)
        if n != s: open(p, 'w', encoding='utf-8').write(n); print('埋めた:', r)
if '--check' in sys.argv: print('\n'.join(left) or '埋め残しなし')
