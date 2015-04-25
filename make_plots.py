#!/usr/bin/env python3

from argparse import ArgumentParser, RawDescriptionHelpFormatter
from pathlib import Path
from util import algorithms, posint

import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import sys

argparser = ArgumentParser(description='''\
  Generates plots from the log summaries computed by batch_run.py.
''', formatter_class=RawDescriptionHelpFormatter)

argparser.add_argument('datadir',
  help='directory where the log summaries are')
argparser.add_argument('-a', '--plot-all', action='store_true',
  help='produce all plots')
argparser.add_argument('--steps-frequency', action='store_true',
  help='plot: how many times an operation used a certain number of steps')
argparser.add_argument('--stepssum-vs-opcount', action='store_true',
  help='plot: number of steps versus number of executed operations')
argparser.add_argument('--nodesmax-vs-opcount', action='store_true',
  help='plot: how much space to execute a certain number of operations')
argparser.add_argument('--stepssum-vs-history', action='store_true',
  help='plot: total number of steps versus history size')
argparser.add_argument('--nodesmax-vs-history', action='store_true',
  help='plot: required space versus history size')
argparser.add_argument('--stepsavg-vs-history', action='store_true',
  help='plot: average number of steps per operation versus history size')
argparser.add_argument('--stepsavgdev-vs-history', action='store_true',
  help='plot: like --stepsavg-vs-history, but include ±3 Stdev')
argparser.add_argument('--stepsmed-vs-history', action='store_true',
  help='plot: (approx) median number of steps/op versus history size')
argparser.add_argument('--stepsmedmax-vs-history', action='store_true',
  help='plot: median and maximum number of steps/op versus history size')
argparser.add_argument('--history', type=posint, default=10,
  help='for which history to generate *-vs-opcount plots')
argparser.add_argument('--exclude-algorithm', action='append',
  default=[], choices=algorithms,
  help='do not include this algorithm in plots')
argparser.add_argument('--legend-location',
  default=0,
  help='where to place the legend')

datadir = None
history = None
legend_location = None
relabel = { 'best' : 'real-time' }
restyle = { 'amortized' : '--', 'best' : '-', 'gc' : '-.', 'naive' : ':' }

def save_plot(filename):
  plt.legend(loc=legend_location)
  p = Path(datadir, '{}.png'.format(filename))
  sys.stdout.write('saving {}\n'.format(p))
  with p.open('w') as out:
    plt.savefig(out, dpi=256)
  plt.clf()

def gcd(xs): # TODO: search stdlib
  r = None
  for x in xs:
    if r is None:
      r = x
    else:
      while x != 0:
        r, x = x, r % x
  return r

def prepare_histogram(data):
  xs = set()
  for ds in data.values():
    for x, _ in ds:
      xs.add(x)
  step = gcd(xs) # TODO: get rid of this heuristic, by shipping step
  new_xs = list(range(min(xs), max(xs) + step, step))
  new_data = {}
  for a, ds in data.items():
    old_ds = { k : v for k, v in ds }
    # the offset of 1 is for logscale
    new_ds = { k : 1 + (old_ds[k] if k in old_ds else 0) for k in new_xs }
    new_data[a] = sorted(new_ds.items())
  return new_data

def load_data(kind, with_history=True):
  data = {}
  for a in algorithms:
    if a == 'naive' or not with_history:
      name = '{}-{}.json'.format(a, kind)
    else:
      name = '{}-{}-{}.json'.format(a, history, kind)
    with Path(datadir, name).open() as f:
      data[a] = json.load(f)
  return data

def plot_data(f, data):
  for a in sorted(data.keys()):
    ds = data[a]
    l = relabel[a] if a in relabel else a
    s = restyle[a] if a in restyle else '-'
    f(
        [d[0] for d in ds],
        [d[1] for d in ds],
        label=l, linewidth=1, linestyle=s, alpha=0.7)

def plot_steps_frequency():
  data = load_data('steps-freq')
  data = prepare_histogram(data)
  plot_data(plt.semilogy, data) # TODO: try bars, maybe they look better
  plt.xlabel('number of memory references')
  plt.ylabel('number of operations')
  plt.xlim(xmin=0)
  plt.ylim(ymin=1)
  plt.tight_layout()
  save_plot('steps-frequency')

def plot_timeseries(dataname, suffix):
  data = load_data(dataname)
  plot_data(plt.plot, data)
  plt.xlabel('number of operations')
  plt.ylabel('number of {}'.format(dataname))
  plt.xlim(xmin=0)
  plt.ylim(ymin=0)
  save_plot('{}{}-vs-opcount-{}'.format(dataname, suffix, history))

def plot_stepssum_vs_opcount():
  plot_timeseries('steps', 'sum')

def plot_nodesmax_vs_opcount():
  plot_timeseries('nodes', 'max')

def plot_historyseries(dataname, suffix, yaxis=None):
  if yaxis is None:
    yaxis = 'number of {}'.format(dataname)
  data = load_data('{}-{}'.format(dataname, suffix), with_history=False)
  plot_data(plt.plot, data)
  plt.xlabel('history $h$')
  plt.ylabel(yaxis)
  plt.ylim(ymin=0)
  plt.tight_layout()
  save_plot('{}{}-vs-history'.format(dataname, suffix))

def plot_stepssum_vs_history():
  plot_historyseries('steps', 'sum', yaxis='memory references')

def plot_nodesmax_vs_history():
  plot_historyseries('nodes', 'max')

def plot_stepsavg_vs_history():
  plot_historyseries('steps', 'avg', yaxis='memory references per operation')

def plot_stepsmed_vs_history():
  plot_historyseries('steps', 'med')

def plot_stepsavgdev_vs_history():
  avg = load_data('steps-avg', with_history=False)
  dev = load_data('steps-dev', with_history=False)
  delta = -0.3
  for a in algorithms:
    if [d[0] for d in avg[a]] != [d[0] for d in dev[a]]:
      sys.stderr.write('E: mismatched avg/dev. skipping {}.\n'.format(a))
      continue
    plt.errorbar(
        [d[0]+delta for d in avg[a]],
        [d[1] for d in avg[a]], yerr=[3*d[1] for d in dev[a]],
        label=a)
    if len(algorithms) > 1:
      delta += 0.6 / (len(algorithms) - 1)
  plt.xlabel('history')
  plt.ylabel('steps per operation (average±3stdev)')
  plt.ylim(ymin=0)
  save_plot('stepsavgdev-vs-history')

def plot_stepsmedmax_vs_history():
  med = load_data('steps-med', with_history=False)
  max = load_data('steps-max', with_history=False)
  for a in algorithms:
    if [d[0] for d in med[a]] != [d[0] for d in max[a]]:
      sys.stderr.write('E: mismatched med/max. skipping {}.\n'.format(a))
      continue
    xs = [d[0] for d in med[a]]
    ys = [d[1] for d in med[a]]
    zs = [d[1] for d in max[a]]
    L,  = plt.plot(xs, ys, lw=3, label=a)
    plt.plot(xs, zs, lw=L.get_linewidth(), color=L.get_color())
    plt.fill_between(xs, ys, zs, alpha=0.3, facecolor=L.get_color(), lw=0)
  plt.xlabel('history')
  plt.ylabel('steps per operation (median..maximum)')
  plt.xlim(xmin=1)
  save_plot('stepsmedmax-vs-history')


def main():
  global algorithms
  global datadir
  global history
  global legend_location
  args = argparser.parse_args()
  algorithms = set(algorithms) - set(args.exclude_algorithm)
  datadir = args.datadir
  history = args.history
  legend_location = args.legend_location
  plt.rc('font', size=5)
  plt.rc('axes', color_cycle=['r','g','b','y'])
  plt.figure(figsize=(2,2))
  plt.locator_params(axis='x', nbins=5)
  if args.plot_all or args.steps_frequency:
    plot_steps_frequency()
  if args.plot_all or args.stepssum_vs_opcount:
    plot_stepssum_vs_opcount()
  if args.plot_all or args.nodesmax_vs_opcount:
    plot_nodesmax_vs_opcount()
  if args.plot_all or args.stepssum_vs_history:
    plot_stepssum_vs_history()
  if args.plot_all or args.nodesmax_vs_history:
    plot_nodesmax_vs_history()
  if args.plot_all or args.stepsavg_vs_history:
    plot_stepsavg_vs_history()
  if args.plot_all or args.stepsmed_vs_history:
    plot_stepsmed_vs_history()
  if args.plot_all or args.stepsavgdev_vs_history:
    plot_stepsavgdev_vs_history()
  if args.plot_all or args.stepsmedmax_vs_history:
    plot_stepsmedmax_vs_history()

if __name__ == '__main__':
  main()

# vim:sts=2:sw=2:
