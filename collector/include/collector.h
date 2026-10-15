/* SPDX-License-Identifier: GPL-2.0 */
#ifndef COLLECTOR_H
#define COLLECTOR_H

#include <stdint.h>
#include <stdio.h>
#include <bpf/libbpf.h>
#include "event_types.h"

#define MAX_CLI_PIDS 256

struct cfg {
	int  duration_s;            /* 0 = run until SIGINT/SIGTERM          */
	int  window_ms;             /* map-drain period                      */
	int  ringbuf_kb;
	int  npids;                 /* >0 enables the target filter          */
	int  pids[MAX_CLI_PIDS];
	int  enable_proc, enable_sys, enable_res;
	int  verbose;
	char outdir[256];
	char run_id[64];
};

struct outputs {
	FILE *proc, *sys, *res, *met;
};

/* Forward declarations of the generated skeleton types. */
struct syscall_monitor_bpf;
struct process_monitor_bpf;
struct resource_monitor_bpf;

struct loader {
	struct syscall_monitor_bpf  *sys;
	struct process_monitor_bpf  *proc;
	struct resource_monitor_bpf *res;
	struct ring_buffer *rb;
	int targets_fd;
	int stats_fd;               /* bpf_enable_stats(RUN_TIME)            */
	int ncpu;
	int page_fault_enabled;
};

/* loader.c */
int  loader_open(const struct cfg *cfg, struct loader *ld);
int  loader_attach(struct loader *ld);
void loader_close(struct loader *ld);
int  loader_prog_stats(const struct loader *ld, FILE *out);

/* ring_buffer.c / event_decoder.c */
int  rb_setup(struct loader *ld, struct outputs *out);
int  rb_drain(struct loader *ld, int timeout_ms);
void sanitize_comm(const char *in, char *out, size_t n);

/* map_flush.c */
long flush_syscalls(const struct loader *ld, FILE *f, uint64_t ws, uint64_t we);
long flush_cpu(const struct loader *ld, FILE *f, uint64_t ws, uint64_t we);

/* metrics.c */
uint64_t now_ns(void);
uint64_t stat_total(int stats_fd, uint32_t idx, int ncpu);
void metrics_header(FILE *f);
void metrics_row(const struct loader *ld, FILE *f, uint64_t events_seen, long sys_entries);

#endif /* COLLECTOR_H */
