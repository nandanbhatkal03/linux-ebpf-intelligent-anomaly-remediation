/* SPDX-License-Identifier: GPL-2.0 */
/* Wire formats shared by the eBPF programs and the user-space collector.
 * Keep every struct a multiple of 8 bytes: per-CPU map values are read back
 * with 8-byte alignment per CPU slot. */
#ifndef EVENT_TYPES_H
#define EVENT_TYPES_H

#ifndef __VMLINUX_H__
#include <linux/types.h>
#endif
#include "config.h"

enum event_type {
	EVT_FORK = 1,   /* value = child tgid                              */
	EVT_EXEC = 2,   /* value = tid that called exec                    */
	EVT_EXIT = 3,   /* value = raw task->exit_code ((status<<8)|sig)  */
};

/* Ring-buffer record: process lifecycle (sparse, must never be lost). 56 B. */
struct event {
	__u64 timestamp;            /* bpf_ktime_get_ns() = CLOCK_MONOTONIC */
	__u64 value;
	__u32 pid;                  /* tgid (user-space "PID")              */
	__u32 ppid;                 /* parent tgid                          */
	__u32 uid;
	__u32 gid;
	__u32 event_type;
	__u32 _pad;                 /* explicit padding: stable ABI         */
	char  comm[TASK_COMM_LEN];
};

/* Syscall counters are aggregated IN KERNEL (no per-syscall event). */
struct syscall_key {
	__u32 tgid;
	__u32 nr;
};
struct syscall_val {
	__u64 count;
	char  comm[TASK_COMM_LEN];
};

/* Per-process CPU / scheduling accounting. */
struct cpu_val {
	__u64 on_cpu_ns;
	__u64 switches;
	__u64 invol_switches;       /* preempted                             */
	__u64 page_faults;          /* 0 when the tracepoint is unavailable  */
	char  comm[TASK_COMM_LEN];
};

enum stat_idx {
	STAT_RB_DROPPED = 0,        /* ring buffer full -> event lost        */
	STAT_MAP_FAIL   = 1,        /* map insert failed -> sample lost      */
	STAT_MAX
};

#endif /* EVENT_TYPES_H */
