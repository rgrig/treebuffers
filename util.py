algorithms = ['naive', 'gc', 'amortized', 'real-time']

def posint(s):
  i = int(s)
  if not (i > 0):
    raise ValueError
  return i
