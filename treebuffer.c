#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "treebuffer.h"

#define unused(x) ((void)x)
#define M (t->mems += 1)
#define MM (t->mems += 2)
#define MMM (t->mems += 3)
#define MMMM (t->mems += 4)

struct Node {
  Node * parent;
  int children; // the number of x such that (x->parent == this)
  Node * ll, * rl; // left link, right link; used for several lists
  int depth; // distance to root
  Node * representant; // ancestor with (depth % history == 0)
  int active_count; // number of x that are active and x->representant == this
  char seen; // used for garbage collection
  char active;
  int data;

  // NOTE: All lists using |ll| and |rl| are doubly linked, circular, and
  // using a sentinel.

  // TODO: pointer to tree so that I can assert that added nodes aren't already in a tree
};

struct Tree {
  int history;
  enum algo algo;
  Node * active; // list of active nodes
  Node * to_delete;
  FILE * statistics_file;
  int node_count; // only maintained by tb_amortized
  int last_gc_node_count; // only maintained by tb_amortized
  int mems;
};

void tb_start_collecting_statistics(Tree * t, FILE * statistics_file) {
  assert (t);
  assert (statistics_file);
  assert (!t->statistics_file);
  t->statistics_file = statistics_file;
}

void tb_stop_collecting_statistics(Tree * t) {
  assert (t);
  t->statistics_file = 0;
}

void print_statistic(Tree * t, const char * format, ...) {
  if (!t->statistics_file) return;
  va_list ap;
  va_start(ap, format);
  vfprintf(t->statistics_file, format, ap);
  va_end(ap);
}

Node * tb_make_node(int data) {
  Node * r = malloc(sizeof(Node));
  r->parent = 0;
  r->children = 0;
  r->ll = r->rl = r;
  r->depth = -1;
  r->representant = 0;
  r->active_count = 0;
  r->seen = 0;
  r->active = 1;
  r->data = data;
  return r;
}

int tb_get_data(Node * x) {
  return x->data;
}

Tree * tb_initialize(int history, enum algo algo, Node * root) {
  assert (root);
  assert (history > 0);
  Tree * t = malloc(sizeof(Tree));
  t->history = history;
  t->algo = algo;
  t->active = malloc(sizeof(Node));
  t->active->ll = t->active->rl = root;
  root->ll = root->rl = t->active;
  root->depth = 0;
  root->representant = root;
  root->active_count = 1;
  assert (root->active);
  t->to_delete = malloc(sizeof(Node));
  t->to_delete->ll = t->to_delete->rl = t->to_delete;
  t->statistics_file = 0;
  t->node_count = 1;
  t->last_gc_node_count = 1;
  t->mems = 0;
  return t;
}

void cut_parent(Tree * t, Node * y) {
  Node * x = (M, y->parent);
  if (x && (M, --x->children == 0) && !(M, x->active)) {
    assert (x->ll == x); // not in some other list
    assert (x->rl == x);
    x->ll = t->to_delete, MM; x->rl = t->to_delete->rl, MMM;
    x->ll->rl = x->rl->ll = x, MMMM;
  }
  y->parent = 0, M;
}

void delete_one(Tree * t) {
  assert (t);
  Node * x = (MM, t->to_delete->rl);
  if ((M, x == t->to_delete)) return;
  assert (t->algo == tb_real_time);
  x->ll->rl = x->rl, MMM; x->rl->ll = x->ll, MMM;
  x->ll = x->rl = x, MM;
  cut_parent(t, x);
  free(x), M;
  print_statistic(t, "S -1\n");
}

void delete(Tree * t) {
  if (!t) return;
  assert (t->mems == 0);

  // Move |active| into |to_delete|.
  { Node * L = (MM, t->active->ll);
    Node * R = (MM, t->active->rl);
    R->ll = t->to_delete, MM;
    L->rl = t->to_delete->rl, MMM;
    t->active->rl->ll->rl = t->active->rl; t->mems += 6;
    t->active->ll->rl->ll = t->active->ll; t->mems += 6;
    t->active->ll = t->active->rl = t->active; t->mems += 5;
  }

  // Cleanup.
  while (t->to_delete->rl != t->to_delete) delete_one(t);
  print_statistic(t, "TF %d\n", t->mems);
  t->mems = 0;
  free(t->active);
  free(t->to_delete);
  free(t);
}

void gc_todo_parent(Tree * t, Node * y, Node * todo) {
  assert (y);
  Node * x = (M, y->parent);
  if (!x) return;
  if ((M, x->seen)) return;
  x->seen = 1, M;
  x->ll = todo, M; x->rl = todo->rl, MM;
  x->ll->rl = x->rl->ll = x, MMMM;
}

void gc_parent(Tree *, Node *);

void gc_node(Tree * t, Node * x) {
  assert (t);
  assert (x);
  assert (!x->seen);
  assert (!x->active);
  assert (x->children == 0);
  gc_parent(t, x);
  free(x);
  if (t->algo == tb_amortized) --t->node_count, M;
  print_statistic(t, "S -1\n");
}

void gc_parent(Tree * t, Node * y) {
  assert (t);
  assert (y);
  Node * x = (M, y->parent);
  y->parent = 0, M;
  if (x && (M, --x->children == 0) && (M, !x->seen)) {
    gc_node(t, x);
  }
}

void gc(Tree * t) {
  assert (t);
  assert (t->algo == tb_gc || t->algo == tb_amortized);

  for (Node * n = (MM, t->active->rl); (M, n != t->active); (M, n = n->rl)) {
    n->seen = 1, M;
  }
  Node sentinel_a, sentinel_b, sentinel_c;
  Node * now; // being processed now
  Node * todo; // to process after now
  Node * middle; // was processed, but doesn't include active nodes
  now = &sentinel_a; todo = &sentinel_b; middle = &sentinel_c;
  middle->ll = middle->rl = middle, MM;
  now->ll = now->rl = now, MM;
  todo->ll = todo->rl = todo, MM;
  for (Node * n = (MM, t->active->rl); (M, n != t->active); (M, n = n->rl)) {
    gc_todo_parent(t, n, todo);
  }
  for (int layer = 2; (MM, layer < t->history && todo != todo->rl); ++layer) {
    { Node * tmp = now; now = todo; todo = tmp; }
    for (Node * n = (M, now->rl); n != now; (M, n = n->rl)) {
      gc_todo_parent(t, n, todo);
    }

    // Move |now| content into |middle|.
    { Node * nl = (M, now->ll);
      Node * nr = (M, now->rl);
      nr->ll = middle, M;
      nl->rl = middle->rl, MM;
      now->rl->ll->rl = now->rl, MMMM;
      now->ll->rl->ll = now->ll, MMMM;
      now->ll = now->rl = now, MM;
    }
  }
  for (Node * n = (M, todo->rl); n != todo; (M, n = n->rl)) {
    gc_parent(t, n);
  }
  { Node * p, * q;
    for (p = (MM, t->to_delete->rl); p != (M, t->to_delete); p = q) {
      q = p->rl, M;
      gc_node(t, p);
    }
    t->to_delete->rl = t->to_delete->ll = t->to_delete, t->mems += 5;
  }
  assert (now->ll == now);
  assert (now->rl == now);
  for (Node * n = (M, todo->rl); n != todo; (M, n = n->rl)) n->seen = 0, M;
  for (Node * n = (M, middle->rl); n != middle; (M, n = n->rl)) n->seen = 0, M;
  for (Node * n = (MM, t->active->rl); (M, n != t->active); (M, n = n->rl))
    n->seen = 0, M;
  { Node * p, * q;
    for (p = (M, todo->rl); p != todo; p = q) {
      q = p->rl, M;
      p->ll = p->rl = p, MM;
    }
    for (p = (M, middle->rl); p != middle; p = q) {
      q = p->rl, M;
      p->ll = p->rl = p, MM;
    }
  }

  if (t->algo == tb_amortized) {
    t->last_gc_node_count = t->node_count, MM;
  }
}

void tb_add_child(Tree * t, Node * parent, Node * child) {
  assert (t);
  assert (t->mems == 0);
  assert (parent);
  assert (child);
  child->parent = parent, M;
  ++parent->children, M;
  child->ll = t->active, MM; child->rl = t->active->rl, MMM;
  child->ll->rl = child->rl->ll = child, MMMM;
  if (t->algo == tb_amortized) {
    if ((MM, ++t->node_count >= 2 * t->last_gc_node_count)) gc(t);
  } else if (t->algo == tb_real_time) {
    delete_one(t);
    child->depth = parent->depth + 1, MM;
    child->representant =
      (MM, child->depth % t->history == 0)? child : (M, parent->representant); M;
    ++child->representant->active_count, MM;
  }
  print_statistic(t, "S +1\n");
  print_statistic(t, "TA %d\n", t->mems);
  t->mems = 0;
}

void tb_deactivate(Tree * t, Node * n) {
  assert (t);
  assert (t->mems == 0);
  assert (n);
  assert (n->active);
  n->active = 0;
  n->ll->rl = n->rl, MMM; n->rl->ll = n->ll, MMM;
  n->ll = n->rl = n, MM;
  if ((M, n->children == 0)) {
    n->ll = t->to_delete, MM; n->rl = t->to_delete->rl, MMM;
    n->ll->rl = n->rl->ll = n, MMMM;
  }
  if (t->algo == tb_gc) {
    gc(t);
  }
  if (t->algo == tb_real_time) {
    assert (n->representant);
    if ((MM, --n->representant->active_count) == 0) {
      cut_parent(t, n->representant);
    }
  }
  print_statistic(t, "TD %d\n", t->mems);
  t->mems = 0;
}

void tb_expand(Tree * t, Node * parent, Node * children[]) {
  for (Node ** n = children; *n; ++n) tb_add_child(t, parent, *n);
  tb_deactivate(t, parent);
}

void tb_history(Tree * t, Node * node, Node * ancestors[]) {
  assert (t->mems == 0);
  assert (node->active);
  int h = (M, t->history);
  while (node && h--) {
    *ancestors++ = node, M;
    node = node->parent, M;
  }
  *ancestors = 0, M;
  print_statistic(t, "TH %d\n", t->mems);
  t->mems = 0;
}

Node * tb_active(const Tree * t) {
  assert (t);
  if (t->active->rl == t->active) return 0;
  return t->active->rl;
}

// PRE: |n| is in |t| (*not* checked by assertions), and active
Node * tb_next_active(const Tree * t, const Node * n) {
  assert (t);
  assert (n);
  assert (n->active);
  if (n->rl == t->active) return 0;
  return n->rl;
}

