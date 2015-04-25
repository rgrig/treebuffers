#!/usr/bin/env python3

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from collections import defaultdict
from functools import partial
from pathlib import Path
from random import randrange, seed
from subprocess import PIPE, Popen
from tempfile import TemporaryFile
from time import perf_counter, process_time
from util import algorithms, posint

import bz2
import json
import math
import sys

import tracemalloc

Ta, Tb = None, None
def prof_start():
  global Ta, Tb
  assert Ta is None
  Ta, Tb = perf_counter(), process_time()
def prof_stop(kind):
  global Ta, Tb
  sys.stderr.write('{:5.01f} {:5.01f} {}\n'.format(
    perf_counter() - Ta, process_time() - Tb, kind))
  sys.stderr.flush()
  Ta, Tb = None, None

argparser = ArgumentParser(description='''\
  Runs treebuffer with several algorithms, and summarizes logs. The logs
  themselves are removed, because they are huge.
''', formatter_class=RawDescriptionHelpFormatter)

argparser.add_argument('data',
  help='file that contains list of trebuffer operations (may be .bz2)')
argparser.add_argument('-H', '--history', type=posint, default=10,
  help='maximum history to try')
argparser.add_argument('-A', '--algorithm', nargs='+',
  choices=algorithms, default=algorithms,
  help='which algorithms to try')
argparser.add_argument('-E', '--executable', default='../main',
  help='executable')
argparser.add_argument('-O', '--outdir', default='plot_data',
  help='where to put the plot data files')
argparser.add_argument('-P', '--points', type=posint, default=100,
  help='number of points in time series')
argparser.add_argument('-N', '--node-bin', type=posint, default=1,
  help='bin size for nodes histogram')
argparser.add_argument('-S', '--step-bin', type=posint, default=10,
  help='bin size for steps histogram')
argparser.add_argument('-K', '--keep-history', action='store_true',
  help='keep "history" operations; by default, skipped')

def run(program, data, keep_history, history, algorithm):
  prof_start()
  def bz2_open(f):
    return bz2.open(f, 'rt')
  open_data = bz2_open if data.endswith('.bz2') else open
  with open_data(data) as in_file:
    with TemporaryFile() as out_file:
      with Popen([program, '-'], stdin=PIPE, stdout=out_file, universal_newlines=True) as p:
        p.stdin.write('initialize {} {} 0:-1\n'.format(history, algorithm))
        for line in in_file:
          if keep_history or not (len(line) > 0 and line[0] == 'h'):
            p.stdin.write(line)
  prof_stop('run')

def parse_log():
  prof_start()
  node_delta = 0
  with open('treebuffer.stats') as log_file:
    for line in log_file:
      if line[0] == 'S':
        node_delta += int(line[2:])
      else:
        yield (int(line[3:]), node_delta)
        node_delta = 0
  prof_stop('parse_log')
  return


# TODO: nodes histogram takes a alot of memory for naive algo;
#   perhaps adaptively drop it if it gets too big?
def summarize_log(points_count, steps_bin, nodes_bin, outdir, prefix):
  # Should ensure that errors >10% of sampling position happen only with Pr<1%.
  samples_count = math.ceil(
    points_count * (math.log(points_count) + math.log(1/0.01)) / (2 * 0.1))
  index = 0
  samples = [None] * samples_count
  steps_histogram = defaultdict(int)
  #nodes_histogram = defaultdict(int)
  steps_sum = steps_sum2 = steps_max = 0
  nodes_sum = nodes_sum2 = nodes_max = nodes = 1
  for steps, nodes_delta in parse_log():
    nodes += nodes_delta
    steps_histogram[steps // steps_bin * steps_bin] += 1
    #nodes_histogram[nodes // nodes_bin * nodes_bin] += 1
    steps_sum += steps
    nodes_sum += nodes
    steps_sum2 += steps * steps
    #nodes_sum2 += nodes * nodes
    steps_max = max(steps_max, steps)
    nodes_max = max(nodes_max, nodes)
    if randrange(index + 1) < samples_count:
      j = index if index < samples_count else randrange(samples_count)
      samples[j] = (index + 1, steps_sum, nodes_max)
    last = (index + 1, steps_sum, nodes_max)
    index += 1
  if index < samples_count:
    samples = samples[:index]
  k = (index + points_count - 1) // points_count
  samples = [(0, 0, 1)] + sorted(samples) + [last, (index + k, None, None)]
  points = []
  for i in range(1, len(samples)):
    if (samples[i-1][0] + k - 1) // k < (samples[i][0] + k - 1) // k:
      if -(samples[i-1][0] % -k) <= samples[i][0] % k:
        points.append(samples[i-1])
      else:
        points.append(samples[i])
  steps_avg = steps_sum / index
  #nodes_avg = nodes_sum / index
  steps_dev = math.sqrt(steps_sum2 - steps_avg * steps_avg)
  #nodes_dev = math.sqrt(nodes_sum2 - nodes_avg * nodes_avg)
  steps_histogram = sorted(steps_histogram.items())
  #nodes_histogram = sorted(nodes_histogram.items())
  def median(bs):
    i, s = 0, bs[0][1]
    while s <= index // 2:
      i += 1
      s += bs[i][1]
    return bs[i][0]
  steps_med = median(steps_histogram)
  #nodes_med = median(nodes_histogram)
  with Path(outdir, '{}-steps-freq.json'.format(prefix)).open('w') as out:
    json.dump(steps_histogram, out)
  with Path(outdir, '{}-steps.json'.format(prefix)).open('w') as out:
    json.dump([(t, s) for t, s, _ in points], out)
  with Path(outdir, '{}-nodes.json'.format(prefix)).open('w') as out:
    json.dump([(t, n) for t, _, n in points], out)
  return \
    { 'steps-med' : steps_med
    , 'steps-avg' : steps_avg
    , 'steps-dev' : steps_dev
    , 'steps-max' : steps_max
    , 'steps-sum' : steps_sum
#    , 'nodes-med' : nodes_med
#    , 'nodes-avg' : nodes_avg
#    , 'nodes-dev' : nodes_dev
    , 'nodes-max' : nodes_max }


def data_file_stem(name):
  to_remove = ['.bz2', '.in']
  for s in to_remove:
    if name.endswith(s):
      name = name[:-len(s)]
  return name

def dumpmemstats():
  top_stats = tracemalloc.take_snapshot().statistics('lineno')
  for s in top_stats[:20]:
    print(s)

def main():
  global run, summarize_log
  seed(37429)
  args = argparser.parse_args()
  outdir = Path(args.outdir, data_file_stem(args.data))
  if not outdir.exists():
    outdir.mkdir(parents=True)
  summarize_log = \
    partial(summarize_log, args.points, args.step_bin, args.node_bin, outdir)
  run = partial(run, args.executable, args.data, args.keep_history)
  summaries = [{} for _ in range(args.history + 1)]
  run(args.history, 'naive')
  naive_summary = summarize_log('naive')
  for h in range(1, args.history + 1):
    sys.stderr.write('HISTORY {}\n'.format(h))
    sys.stderr.flush()
    summaries[h]['naive'] = naive_summary
    for a in args.algorithm[1:]:
      run(h, a)
      summaries[h][a] = summarize_log('{}-{}'.format(a, h))
  prof_start()
  for a in algorithms:
    keys = sorted(summaries[1][a].keys())
    for k in keys:
      with Path(outdir, '{}-{}.json'.format(a, k)).open('w') as out:
        json.dump(
            [(h, summaries[h][a][k]) for h in range(1, args.history + 1)], out)
  prof_stop('save_across_history')
  #dumpmemstats()

if __name__ == '__main__':
  main()

# vim:sts=2:sw=2:
