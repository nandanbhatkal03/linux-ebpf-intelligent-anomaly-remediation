// SPDX-License-Identifier: GPL-2.0
/* Resource monitor: per-process on-CPU time, context switches (voluntary vs
 * preempted) and user page faults, aggregated in kernel. CPU time is exact:
 * on every sched_switch the time since the previous switch on THIS CPU is
 * charged to the task being switched out. */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
#include "event_maps.h"

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, 1);
	__type(key, __u32);
	__type(value, __u64);
} last_switch_ts SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_LRU_PERCPU_HASH);
	__uint(max_entries, CPU_MAP_SIZE);
	__type(key, __u32);
	__type(value, struct cpu_val);
} cpu_stats SEC(".maps");

/* 1 = charge on-CPU time at sched_switch (fallback); 0 = sched_stat_runtime does it. Switch-time charging
 * misses a CPU hog that is never switched out (e.g. a lone spinning process), so the loader prefers
 * the sched_stat_runtime tracepoint, which fires on every scheduler tick and context switch. */
const volatile __u8 accrue_in_switch = 1;

static __always_inline struct cpu_val *get_val(__u32 tgid, struct task_struct *t)
{
	struct cpu_val *v = bpf_map_lookup_elem(&cpu_stats, &tgid);

	if (v)
		return v;
	struct cpu_val nv = {};
	if (t)
		BPF_CORE_READ_STR_INTO(&nv.comm, t, comm);
	else
		bpf_get_current_comm(&nv.comm, sizeof(nv.comm));
	bpf_map_update_elem(&cpu_stats, &tgid, &nv, BPF_NOEXIST);
	v = bpf_map_lookup_elem(&cpu_stats, &tgid);
	if (!v)
		stat_inc(STAT_MAP_FAIL);
	return v;
}

SEC("tp_btf/sched_switch")
int BPF_PROG(on_switch, bool preempt, struct task_struct *prev,
	     struct task_struct *next)
{
	__u32 zero = 0;
	__u64 now = bpf_ktime_get_ns();
	__u64 *last = bpf_map_lookup_elem(&last_switch_ts, &zero);

	if (!last)
		return 0;
	__u64 prev_ts = *last;
	*last = now;
	if (!prev_ts)
		return 0;               /* first switch seen on this CPU */

	__u32 tgid = BPF_CORE_READ(prev, tgid);

	if (!is_monitored(tgid))
		return 0;
	struct cpu_val *v = get_val(tgid, prev);
	if (!v)
		return 0;
	if (accrue_in_switch)
		v->on_cpu_ns += now - prev_ts;
	v->switches++;
	if (preempt)
		v->invol_switches++;
	return 0;
}

/* Exact runtime accounting: runs on every update_curr() of the running task. */
SEC("?tracepoint/sched/sched_stat_runtime")
int on_runtime(struct trace_event_raw_sched_stat_runtime *ctx)
{
	__u32 tgid = bpf_get_current_pid_tgid() >> 32;

	if (!is_monitored(tgid))
		return 0;
	struct cpu_val *v = get_val(tgid, NULL);
	if (v)
		v->on_cpu_ns += ctx->runtime;
	return 0;
}

/* Optional: only present on kernels exposing exceptions:page_fault_user. The
 * loader enables autoload after checking tracefs. */
SEC("?tracepoint/exceptions/page_fault_user")
int on_page_fault(void *ctx)
{
	__u32 tgid = bpf_get_current_pid_tgid() >> 32;

	if (!is_monitored(tgid))
		return 0;
	struct cpu_val *v = get_val(tgid, NULL);
	if (v)
		v->page_faults++;
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
