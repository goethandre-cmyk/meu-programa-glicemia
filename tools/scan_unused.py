"""
Scan for Python function definitions and count references across the repo.
Writes a candidate list to tools/unused_candidates.txt where reference count == 1 (definition only).
Use this output as a starting point for manual review before removing anything.
"""
import ast
import glob
import os
import re
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT_PATH = os.path.join(ROOT, 'tools', 'unused_candidates.txt')

print('Repo root:', ROOT)

py_files = [f for f in glob.glob(os.path.join(ROOT, '**', '*.py'), recursive=True)]
# ignore virtual envs, __pycache__ and tools output
py_files = [p for p in py_files if ('\\venv\\' not in p and '/venv/' not in p and '__pycache__' not in p and p.startswith(ROOT))]

# read file contents
contents = {}
for p in py_files:
    try:
        with open(p, 'r', encoding='utf-8') as fh:
            contents[p] = fh.read()
    except Exception as e:
        print('skip', p, 'err', e)

# find function definitions using ast for accuracy
defs = []  # (name, file, lineno)
for p, src in contents.items():
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # skip files with syntax errors
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            name = node.name
            # skip tests helper constructors and common small helpers? we'll include all and let human filter
            defs.append((name, p, node.lineno))

# create big text for counting
all_text = '\n'.join(contents.values())

# count references by simple word boundary regex
counts = defaultdict(int)
for name, p, ln in defs:
    # count occurrences across all files
    pattern = r'\\b' + re.escape(name) + r'\\b'
    counts[(name, p, ln)] = len(re.findall(pattern, all_text))

# produce candidates where count == 1 (only definition)
candidates = []
for key, c in counts.items():
    name, p, ln = key
    # heuristics exclusions: skip magic methods, functions starting with 'test_' (test cases), and names used in templates?
    if name.startswith('__'):
        continue
    if name.startswith('test_'):
        continue
    if c <= 1:
        candidates.append((name, p, ln, c))

# sort by count then name
candidates.sort(key=lambda x: (x[3], x[0]))

with open(OUT_PATH, 'w', encoding='utf-8') as out:
    out.write('Candidates for manual review (count == 1)\n')
    out.write('Format: function_name | file | lineno | reference_count\n\n')
    for name, p, ln, c in candidates:
        out.write(f'{name} | {os.path.relpath(p, ROOT)} | {ln} | {c}\n')

print('\nWrote', OUT_PATH)
print('Candidates count:', len(candidates))
print('\nTop 40 candidates:')
for i, (name, p, ln, c) in enumerate(candidates[:40], 1):
    print(f'{i:02d}. {name}  ({c})  - {os.path.relpath(p, ROOT)}:{ln}')

print('\nDone. Review tools/unused_candidates.txt before removing anything.')
