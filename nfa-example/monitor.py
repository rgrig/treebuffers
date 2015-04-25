#!/usr/bin/env python3

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import defaultdict
from functools import partial

import ast
import bz2
import json
import re
import sys

argparser = ArgumentParser(description='''\
  From an NFA description and a text file, produce a test for treebuffer.
''', formatter_class=RawDescriptionHelpFormatter)

def write_file(s):
  return open(s, 'w')
def posint(t):
  r = int(t)
  if not (r > 0):
    raise ValueError
  return r

argparser.add_argument('nfa',
  help='file with the NFA')
argparser.add_argument('text',
  help='the text to process')
argparser.add_argument('-o', type=write_file, default=sys.stdout,
  help='where to write the result (default is stdout)')
argparser.add_argument('-H', type=posint, default=10,
  help='history length')
argparser.add_argument('-A', default='naive',
  choices=['naive', 'gc', 'amortized', 'real-time'],
  help='algorithm')

def check(b, m):
  if not b:
    sys.stderr.write('E: {}\n'.format(m))
    sys.exit(1)

def parse_nfa(nfa_file):
  nfa = []
  kwd_re = re.compile('([a-zA-Z0-9_]+) +')
  with open(nfa_file) as f:
    for line in f:
      line = line.strip()
      if line.startswith('#') or line == '':
        continue
      i = 0
      m = kwd_re.match(line, i)
      check(m, 'cannot parse: {}'.format(line))
      source = m.group(1)
      i = m.end()
      m = kwd_re.match(line, i)
      check(m, 'cannot parse: {}'.format(line))
      target = m.group(1)
      i = m.end()
      m = kwd_re.match(line, i)
      check(m, 'cannot parse: {}'.format(line))
      kind = m.group(1)
      check(kind in ['relevant', 'irrelevant'], 'bad type: {}'.format(kind))
      i = m.end()
      if line[i:] == 'other':
        letters = None
      else:
        letters = ast.literal_eval(line[i:])
        check(type(letters) == str, 'label is not string: {}'.format(letters))
      nfa.append((source, target, kind, letters))
  return nfa

# From list of transitions, to hashtable.
def index_nfa(nfa):
  result = defaultdict(partial(defaultdict, list))
  for source, target, type, letters in nfa:
    if letters is None:
      result[source][None].append((type, target))
    else:
      for alpha in letters:
        result[source][alpha].append((type, target))
  return result

used_ids = set()

def allocate_node_id():
  i = 0
  while i in used_ids:
    i += 1
  used_ids.add(i)
  return i

def free_node_id(i):
  used_ids.remove(i)

def main():
  args = argparser.parse_args()
  out = args.o
  nfa = index_nfa(parse_nfa(args.nfa))
  root_id = allocate_node_id()
  leaves = { root_id : [] }
  error_ids = set()
  def add_child(parent_id, child_id, child_data):
    assert parent_id in used_ids
    assert child_id in used_ids
    out.write('add_child {} {}:{}\n'.format(parent_id, child_id, child_data))
  def node_done(x):
    assert x in used_ids
    if x in error_ids:
      out.write('history {}\n'.format(x))
      error_ids.remove(x)
    out.write('deactivate {}\n'.format(x))
    free_node_id(x)
  now, nxt = None, set([('start', root_id, False)])
  open_file = bz2.open if args.text.endswith('.bz2') else open
  with open_file(args.text, mode='rt', encoding='utf-8', errors='ignore') as f:
    out.write('initialize {} {} {}:-1\n'.format(args.H, args.A, root_id))
    position = -1
    while True:
      position += 1
      alpha = f.read(1)
      if len(alpha) != 1:
        break
      now, nxt = nxt, set()
      for source, parent_id, saw_error in now:
        transitions = nfa[source][alpha]
        if transitions == []:
          transitions = nfa[source][None]
        for type, target in transitions:
          if type == 'irrelevant':
            nxt.add((target, parent_id, saw_error or target == 'error'))
          elif type == 'relevant':
            child_id = allocate_node_id()
            if saw_error or target == 'error':
              error_ids.add(child_id)
            nxt.add((target, child_id, False))
            add_child(parent_id, child_id, position)
          else:
            assert False
      for x in set(k for _, k, _ in now) - set(k for _, k, _ in nxt):
        node_done(x)
    for x in set(x for _, x, _ in nxt ):
      node_done(x)
    assert len(error_ids) == 0
    out.write('# done\n')

if __name__ == '__main__':
  main()
