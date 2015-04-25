#!/usr/bin/env python3

from pathlib import Path
from subprocess import PIPE, Popen, STDOUT
from urllib.request import urlopen

import os
import sys

server_url = 'https://s3-eu-west-1.amazonaws.com/tree-buffers/datasets'

def download_dataset(dataset):
  os.makedirs('datasets', exist_ok=True)
  url = '{}/{}.in.bz2'.format(server_url, dataset)
  path = 'datasets/{}.in.bz2'.format(dataset)
  if Path(path).exists():
    sys.stdout.write('  file {} exists, not downloading\n'.format(path))
    return
  with urlopen(url) as r:
    file_size = int(r.getheader("Content-Length"))
    sys.stdout.write('  downloading {}\n    (takes 20 #s to finish)\n'.format(url))
    sys.stdout.write('    {:.1f}MiB: '.format(file_size/2**20))
    sys.stdout.flush()
    with open(path, 'wb') as w:
      while True:
        buffer = r.read(file_size // 20 + 1)
        if not buffer:
          break
        w.write(buffer)
        sys.stdout.write('#')
        sys.stdout.flush()
  sys.stdout.write('\n')

def run(command):
  sys.stdout.write('    executing command: {}\n'.format(' '.join(command)))
  with Popen(command, stdout=PIPE, stderr=STDOUT, bufsize=0, universal_newlines=True) as p:
    for line in p.stdout:
      sys.stdout.write('      {}'.format(line))
      sys.stdout.flush()

def batch_run(dataset):
  if Path('logs/datasets/{}'.format(dataset)).exists():
    sys.stdout.write('  logs/datasets/{} exists, not running batch_run.py\n'.format(dataset))
    return
  sys.stdout.write('  running experiments and summarizing logs\n')
  command = \
    [ './batch_run.py'
    , 'datasets/{}.in.bz2'.format(dataset)
    , '-H', '100'
    , '-O', 'logs'
    , '-E', './main' ]
  run(command)

def make_plots(dataset):
  os.makedirs('plots', exist_ok=True)
  todo =\
    [ ( 'stepsavg-vs-history', [], 'runtime' )
    , ( 'stepsavg-vs-history', ['--exclude-algorithm', 'gc'], 'runtime-nogc' )
    , ( 'steps-frequency', ['--history', '100'], 'runtime-perop')
    , ( 'nodesmax-vs-history', ['--exclude-algorithm', 'naive'], 'memory') ]
  sys.stdout.write('  making plots\n')
  for a, bs, c in todo:
    run(['./make_plots.py', '--{}'.format(a), 'logs/datasets/{}'.format(dataset)] + bs)
    run(['cp', 'logs/datasets/{}/{}.png'.format(dataset, a), 'plots/{}-{}.png'.format(dataset, c)])

def main():
  run(['make'])
  for d in [ "chain", "dacapo-hasnext", "wikipedia" ]:
    sys.stdout.write('processing {}\n'.format(d))
    download_dataset(d)
    batch_run(d)
    make_plots(d)

if __name__ == '__main__':
  main()
