#if !defined TREEBUFFER_H
#define TREEBUFFER_H

#include <stdio.h>

enum algo { tb_naive = 0, tb_gc, tb_amortized, tb_real_time };

typedef struct Node Node;
typedef struct Tree Tree;

Node * tb_make_node(int data);
int tb_get_data(Node * node);
Tree * tb_initialize(int history, enum algo algo, Node * root);
void delete(Tree * tree);

/* NOTE: The client must allocate/deallocate the 0-terminated arrays |children|
and |ancestors| that appear below. In contrast, clients allocate but do not
deallocate |Node|s. */

void tb_add_child(Tree * tree, Node * parent, Node * child);
void tb_deactivate(Tree * tree, Node * node);
void tb_expand(Tree * tree, Node * parent, Node * children[]);
void tb_history(Tree * tree, Node * node, Node * ancestors[]);
  /* history of |node| is put in |ancestors|, which is 0-terminated;
     |node| must be active */

Node * tb_active(const Tree * tree);
Node * tb_next_active(const Tree * tree, const Node * node);
  // Intended use:
  //   for (Node * n = tb_active(t); n; n = tb_next_active(t, n)) { ... }

void tb_start_collecting_statistics(Tree * tree, FILE * statistics_file);
void tb_stop_collecting_statistics(Tree * tree);

#endif
