#include <assert.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "treebuffer.h"

#define buffer_size (1 << 10)
#define active_size (1 << 20)
#define children_size (1 << 20)

typedef char * (*read_t)(void);
FILE * input_file;
read_t read;
FILE * statistics_file;

Tree * tree;
Node * active[active_size]; // TODO: replace by hashtable
Node * children[children_size];
int children_id[children_size];
int children_data[children_size];

void reset() {
  delete(tree);
  memset(active, 0, sizeof(active));
}

// TODO: don't exit on these errors (annoying for interactive use)
int check_node_id_range(int node_id) {
  if (0 <= node_id && node_id < active_size) return 1;
  fprintf(stderr, "W: node id outside [0.. %d).\n", active_size);
  return 0;
}

int check_node_id_is_old(int node_id) {
  if (active[node_id]) return 1;
  fprintf(stderr, "E: %d is not old.\n", node_id);
  return 0;
}

int check_node_id_is_new(int node_id) {
  if (!active[node_id]) return 1;
  fprintf(stderr, "E: %d is not new.\n", node_id);
  return 0;
}

Node * get_new_node(int node_id, int node_data) {
  if (!(check_node_id_range(node_id) && check_node_id_is_new(node_id))) {
    return 0;
  }
  return active[node_id] = tb_make_node(node_data);
}

Node * get_old_node(int node_id) {
  if (!(check_node_id_range(node_id) && check_node_id_is_old(node_id))) {
    return 0;
  }
  return active[node_id];
}

void remove_old_node(int node_id) {
  check_node_id_range(node_id);
  check_node_id_is_old(node_id);
  active[node_id] = 0;
}

char * get_line_from_file() {
  char * buffer = calloc(buffer_size, sizeof(char));
  assert (buffer);
  char * r = fgets(buffer, buffer_size, input_file);
  if (!r) {
    free(buffer);
    return 0;
  }
  assert (r == buffer);
  while (*r) ++r;
  --r;
  if (*r != '\n') {
    fprintf(stderr, "E: line buffer too small.");
    fprintf(stderr, " Increase buffer_size and recompile.\n");
    exit(2);
  } else {
    *r = 0;
  }
  return buffer;
}

char * get_line_with_prompt() {
  // I wanted to use readline here, but "ledit ./main" works better.
  printf("> ");
  fflush(stdout);
  return get_line_from_file();
}

char * command_list[] =
  { "initialize", "add_child", "deactivate", "expand", "history", "help", 0 };
char * algorithm_list[] =
  { "naive", "gc", "amortized", "real-time", 0 };

int parse_enum(const char * s, char * vs[]) {
  int result = -1;
  for (int i = 0; vs[i]; ++i) {
    const char * p = s;
    const char * q = vs[i];
    while (*p && !isspace(*p) && *q && *p == *q) { ++p; ++q; }
    if (isspace(*p) || !*q) {
      if (result != -1) {
        fprintf(stderr, "W: %s matches both %s and %s.", s, vs[result], vs[i]);
        fprintf(stderr, " Ignoring.\n");
        return -2;
      }
      result = i;
    }
  }
  if (result == -1) {
    fprintf(stderr, "W: %s doesn't match either of:", s);
    for (int i = 0; vs[i]; ++i) fprintf(stderr, " %s", vs[i]);
    fprintf(stderr, ". Ignoring.\n");
  }
  return result;
}

bool parse_node(const char ** p, int * id, int * data) {
  int n;
  if (sscanf(*p, "%d%n", id, &n) != 1) return false;
  *p += n;
  *data = *id;
  if (sscanf(*p, ":%d%n", data, &n) == 1) *p += n;
  return true;
}

void do_initialize(const char * p) {
  int history;
  enum algo algo;
  int root_id, root_data;

  int i;
  if (sscanf(p, "%d %n", &history, &i) < 1) {
    fprintf(stderr, "W: Cannot parse history. Ignoring %s.\n", p);
    return;
  }
  if (history < 0) {
    fprintf(stderr, "W: Negative history (%d) ignored.\n", history);
    return;
  }
  if (history >= children_size) {
    fprintf(stderr, "W: history too big. Increase children_size and recompile.\n");
    return;
  }
  p += i;
  switch(parse_enum(p, algorithm_list)) {
  case -1: return;
  case 0: algo = tb_naive; break;
  case 1: algo = tb_gc; break;
  case 2: algo = tb_amortized; break;
  case 3: algo = tb_real_time; break;
  default: assert (0);
  }
  while (*p && !isspace(*p)) ++p;
  while (isspace(*p)) ++p;
  if (!parse_node(&p, &root_id, &root_data)) {
    fprintf(stderr, "W: Cannot parse root id. Ignoring %s.\n", p);
    return;
  }

  reset();
  Node * root = get_new_node(root_id, root_data);
  if (!root) {
    fprintf(stderr, "W: Invalid root.\n");
    return;
  }
  tree = tb_initialize(history, algo, root);
  if (statistics_file) tb_start_collecting_statistics(tree, statistics_file);
}

void do_add_child(const char * p) {
  int child_id, child_data;
  int parent_id;
  int n;

  if (sscanf(p, "%d%n", &parent_id, &n) != 1) {
    fprintf(stderr, "W: Can't parse parent id, in add_child. Ignoring %s.\n", p);
    return;
  }
  p += n;
  if (!parse_node(&p, &child_id, &child_data)) {
    fprintf(stderr, "W: Can't parse child, in add_child. Ignoring %s.\n", p);
    return;
  }
  Node * parent = get_old_node(parent_id);
  Node * child = get_new_node(child_id, child_data);
  if (!parent) fprintf(stderr, "W: Invalid parent node id.\n");
  if (!child) fprintf(stderr, "W: Invalid child node.\n");
  if (!parent || !child) return;
  tb_add_child(tree, parent, child);
}

void do_deactivate(const char * p) {
  int parent_id;
  if (sscanf(p, "%d", &parent_id) != 1) {
    fprintf(stderr, "W: Can't parse node id, in deactivate. Ignoring %s.\n", p);
    return;
  }
  Node * parent = get_old_node(parent_id);
  if (!parent) {
    fprintf(stderr, "W: Invalid node id.\n");
    return;
  }
  tb_deactivate(tree, parent);
  remove_old_node(parent_id);
}

void do_expand(const char * p) {
  int i;
  int parent_id;
  int n;

  if (sscanf(p, "%d%n", &parent_id, &n) < 1) {
    fprintf(stderr, "W: Cannot parse parent id to expand. Ignoring %s.\n", p);
    return;
  }
  p += n;
  i = 0;
  for (i = 0; i < children_size && parse_node(&p, &children_id[i], &children_data[i]); ++i);
  if (i >= children_size) {
    fprintf(stderr, "W: Too many children. Increase children_size and recompile.\n");
  }
  int bad = 0;
  for (int j = 0; j < i; ++j) {
    children[j] = get_new_node(children_id[j], children_data[j]);
    if (!children[j]) {
      fprintf(stderr, "W: The child node at index %d is invalid.\n", j);
      ++bad;
    }
  }
  Node * parent = get_old_node(parent_id);
  if (!parent) fprintf(stderr, "W: Invalid parent id.\n");
  if (i >= children_size || bad > 0 || !parent) {
    for (int j = 0; j < i; ++ j) if (!children_id[j]) {
      remove_old_node(children_id[j]);
    }
    return;
  }
  children[i] = 0;
  tb_expand(tree, parent, children);
  remove_old_node(parent_id);
}

void do_history(const char * p) {
  int node_id;
  if (sscanf(p, "%d", &node_id) < 1) {
    fprintf(stderr, "W: no node id after history command. Ignoring %s.\n", p);
    return;
  }
  Node * node = get_old_node(node_id);
  if (!node) {
    fprintf(stderr, "W: Invalid node id.\n");
    return;
  }
  tb_history(tree, node, children);
  printf("H:");
  for (int i = 0; children[i]; ++i) printf(" %d", tb_get_data(children[i]));
  printf("\n");
}

void print_help() {
  printf("COMMANDS:\n");
  printf("  initialize HISTORY ALGORITHM ROOT_ID[:ROOT_DATA]\n");
  printf("  add_child PARENT_ID NEW_ID[:NEW_DATA]\n");
  printf("  deactivate NODE_ID\n");
  printf("  expand PARENT_ID NEW_ID1[:NEW_DATA1] NEW_ID2[:NEW_DATA2] ...\n");
  printf("  history NODE_ID\n");
  printf("  help\n");
  printf("  morehelp\n");
  printf("ALGORITHM is one of: naive gc amortized real-time\n");
  printf("IDs and DATA are integers\n");
}

void process() {
  char * line;
  char * p;
  while ((line = read())) {
    for (p = line; isspace(*p); ++p);
    if (!*p || *p == '#') continue;
    int command_index = parse_enum(p, command_list);
    if (command_index < 0) continue;
    while (*p && !isspace(*p)) ++p;
    while (isspace(*p)) ++p;
    switch (command_index) {
    case 0: do_initialize(p); break;
    case 1: do_add_child(p); break;
    case 2: do_deactivate(p); break;
    case 3: do_expand(p); break;
    case 4: do_history(p); break;
    case 5: print_help(p); break;
    default:
      assert (0);
    }
    free(line);
  }
}

bool read_stdin = false;

void set_read_stdin() {
  if (read_stdin) {
    fprintf(stderr, "E: Can't read stdin multiple times.\n");
    exit(1);
  }
  read_stdin = true;
}

int main(int argc, char * argv[]) {
  statistics_file = fopen("treebuffer.stats", "w");
  if (!statistics_file)
    fprintf(stderr, "W: cannot write to treebuffer.stats\n");
  for (int i = 1; i < argc; ++i) {
    if (strcmp(argv[i], "-")) {
      input_file = fopen(argv[i], "r");
    } else {
      input_file = stdin;
      set_read_stdin();
    }
    if (!input_file) {
      fprintf(stderr, "E: Cannot process %s. Skipping.\n", argv[i]);
      continue;
    }
    read = get_line_from_file;
    process();
    fclose(input_file);
  }
  if (argc == 1) {
    input_file = stdin;
    read = get_line_with_prompt;
    process();
    printf("\n");
  }
  if (statistics_file) {
    fflush(statistics_file);
    fclose(statistics_file);
  }
}
