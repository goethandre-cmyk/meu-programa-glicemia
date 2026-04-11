"""
Simple helper: list function definitions across the repo and count textual references.
Outputs candidate lines: <function_name>|<ref_count>|<def_file>

Use this as a conservative first-pass: it treats any textual occurrence as a reference
and therefore may mark dynamic uses (templates, getattr, string-based calls) as unused
if they don't have textual references. Always review before removing.
"""
import glob
import re
import sys
from collections import Counter

ROOT_GLOB = "**/*.py"

pattern = re.compile(r'^\s*def\s+([A-Za-z_]\w*)\s*\(', re.M)

files = [f for f in glob.glob(ROOT_GLOB, recursive=True) if '/.venv/' not in f.replace('\\','/')]
all_text = ''
file_contents = {}
for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            s = fh.read()
    except Exception as e:
        # skip unreadable
        continue
    file_contents[f] = s
    all_text += '\n' + s

definitions = []  # (name, file)
for f, s in file_contents.items():
    for m in pattern.finditer(s):
        definitions.append((m.group(1), f))

# Count textual occurrences in whole repo
counts = Counter()
for name, _ in definitions:
    # use word boundary to avoid partial matches
    counts[name] = len(re.findall(r'\b' + re.escape(name) + r'\b', all_text))

# Prepare candidates: functions with count <= 1 (only definition)
candidates = [(n, counts[n], f) for n, f in definitions if counts[n] <= 1]
# Sort by count then name
candidates.sort(key=lambda x: (x[1], x[0]))

out_path = 'tools/unused_candidates.txt'
with open(out_path, 'w', encoding='utf-8') as out:
    out.write('function|count|defined_in\n')
    for n, c, f in candidates:
        out.write(f'{n}|{c}|{f}\n')

print(f'Wrote {len(candidates)} candidate(s) to {out_path}')
print('Top 50 shown below:')
for row in candidates[:50]:
    print(f'{row[0]} | {row[1]} | {row[2]}')

# exit code 0
sys.exit(0)
