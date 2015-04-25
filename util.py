algorithms = ['naive', 'gc', 'amortized', 'best']

def posint(s):
  i = int(s)
  if not (i > 0):
    raise ValueError
  return i
