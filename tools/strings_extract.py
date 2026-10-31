import sys, os, re

def extract(data, minlen=5):
    # ASCII printable
    ascii_pat = re.compile(rb'[\x20-\x7e]{%d,}' % minlen)
    # UTF-16LE: printable ASCII pairs -> decode
    utf16_pat = re.compile(rb'(?:[\x20-\x7e]\x00){%d,}' % minlen)
    out = []
    for m in ascii_pat.finditer(data):
        s = m.group().decode('ascii', 'replace')
        out.append(('A', s))
    for m in utf16_pat.finditer(data):
        raw = m.group()
        s = raw.decode('utf-16-le', 'replace')
        out.append(('U', s))
    return out

def run(path):
    with open(path, 'rb') as f:
        data = f.read()
    strings = extract(data)
    base = os.path.basename(path)
    with open(base + '.str.txt', 'w', encoding='utf-8', errors='replace') as o:
        seen = set()
        for kind, s in strings:
            if s in seen:
                continue
            seen.add(s)
            o.write("%s\t%s\n" % (kind, s))
    print("%s: %d unique strings" % (base, len(seen)))

for p in sys.argv[1:]:
    try:
        run(p)
    except Exception as e:
        print("FAIL", p, e)
