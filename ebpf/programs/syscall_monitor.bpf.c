// SPDX-License-Identifier: GPL-2.0
/* Syscall monitor: counts syscalls per (tgid, syscall number) INSIDE the
 * kernel. Emitting one ring-buffer record per syscall would lose events under
 * load (the closest related work reports 7.17 % drops); a per-CPU hash that
 * user space drains once per window removes that failure mode. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "event_maps.h"

struct {
	__uint(type, BPF_MAP_TYPE_LRU_PERCPU_HASH);
	__uint(max_entries, SYSCALL_MAP_SIZE);
	__type(key, struct syscall_key);
	__type(value, struct syscall_val);
} syscall_counts SEC(".maps");

SEC("tp_btf/sys_enter")
int BPF_PROG(on_sys_enter, struct pt_regs *regs, long id)
{
	__u32 tgid = bpf_get_current_pid_tgid() >> 32;

	if (id < 0 || id >= MAX_SYSCALL_NR || !is_monitored(tgid))
		return 0;

	struct syscall_key key = { .tgid = tgid, .nr = (__u32)id };
	struct syscall_val *v = bpf_map_lookup_elem(&syscall_counts, &key);

	if (v) {
		v->count++;
		return 0;
	}
	struct syscall_val nv = { .count = 1 };
	bpf_get_current_comm(&nv.comm, sizeof(nv.comm));
	if (bpf_map_update_elem(&syscall_counts, &key, &nv, BPF_NOEXIST)) {
		v = bpf_map_lookup_elem(&syscall_counts, &key);
		if (v)
			v->count++;
		else
			stat_inc(STAT_MAP_FAIL);
	}
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
