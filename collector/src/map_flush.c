// SPDX-License-Identifier: GPL-2.0
/* Drains the in-kernel aggregation maps once per window (read-and-clear). */
#include <stdlib.h>
#include <bpf/bpf.h>
#include "collector.h"

int loader_syscall_map_fd(const struct loader *ld);
int loader_cpu_map_fd(const struct loader *ld);

static int use_lookup_and_delete = 1;

/* Atomically read+remove one element; fall back to lookup+delete on kernels
 * where lookup_and_delete is unsupported for per-CPU LRU hash maps. */
static int take(int fd, const void *key, void *buf)
{
	if (use_lookup_and_delete) {
		if (!bpf_map_lookup_and_delete_elem(fd, key, buf))
			return 0;
		use_lookup_and_delete = 0;
	}
	if (bpf_map_lookup_elem(fd, key, buf))
		return -1;
	bpf_map_delete_elem(fd, key);
	return 0;
}

long flush_syscalls(const struct loader *ld, FILE *f, uint64_t ws, uint64_t we)
{
	int fd = loader_syscall_map_fd(ld);
	struct syscall_key *keys, cur, next;
	struct syscall_val *vals;
	long n = 0, rows = 0;

	if (fd < 0 || !f)
		return 0;
	keys = malloc(SYSCALL_MAP_SIZE * sizeof(*keys));
	vals = calloc(ld->ncpu, sizeof(*vals));
	if (!keys || !vals)
		goto out;
	/* Snapshot keys first: deleting while iterating would restart the walk. */
	int err = bpf_map_get_next_key(fd, NULL, &next);
	while (!err && n < SYSCALL_MAP_SIZE) {
		keys[n++] = next;
		cur = next;
		err = bpf_map_get_next_key(fd, &cur, &next);
	}
	for (long i = 0; i < n; i++) {
		unsigned long long total = 0;
		char comm[TASK_COMM_LEN + 1] = "?";

		if (take(fd, &keys[i], vals))
			continue;
		for (int c = 0; c < ld->ncpu; c++) {
			total += vals[c].count;
			if (vals[c].count && comm[0] == '?')
				sanitize_comm(vals[c].comm, comm, sizeof(comm));
		}
		if (!total)
			continue;
		fprintf(f, "%llu,%llu,%u,%s,%u,%llu\n", (unsigned long long)ws,
			(unsigned long long)we, keys[i].tgid, comm, keys[i].nr, total);
		rows++;
	}
out:
	free(keys);
	free(vals);
	return rows;
}

long flush_cpu(const struct loader *ld, FILE *f, uint64_t ws, uint64_t we)
{
	int fd = loader_cpu_map_fd(ld);
	__u32 *keys, cur, next;
	struct cpu_val *vals;
	long n = 0, rows = 0;

	if (fd < 0 || !f)
		return 0;
	keys = malloc(CPU_MAP_SIZE * sizeof(*keys));
	vals = calloc(ld->ncpu, sizeof(*vals));
	if (!keys || !vals)
		goto out;
	int err = bpf_map_get_next_key(fd, NULL, &next);
	while (!err && n < CPU_MAP_SIZE) {
		keys[n++] = next;
		cur = next;
		err = bpf_map_get_next_key(fd, &cur, &next);
	}
	for (long i = 0; i < n; i++) {
		unsigned long long ns = 0, sw = 0, inv = 0, pf = 0;
		char comm[TASK_COMM_LEN + 1] = "?";

		if (take(fd, &keys[i], vals))
			continue;
		for (int c = 0; c < ld->ncpu; c++) {
			ns += vals[c].on_cpu_ns;
			sw += vals[c].switches;
			inv += vals[c].invol_switches;
			pf += vals[c].page_faults;
			if (vals[c].switches + vals[c].page_faults && comm[0] == '?')
				sanitize_comm(vals[c].comm, comm, sizeof(comm));
		}
		if (!ns && !sw && !pf)
			continue;
		fprintf(f, "%llu,%llu,%u,%s,%llu,%llu,%llu,%llu\n", (unsigned long long)ws,
			(unsigned long long)we, keys[i], comm, ns, sw, inv, pf);
		rows++;
	}
out:
	free(keys);
	free(vals);
	return rows;
}
