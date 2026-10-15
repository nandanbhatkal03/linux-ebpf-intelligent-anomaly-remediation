// SPDX-License-Identifier: GPL-2.0
/* Process-lifecycle monitor: fork / exec / exit as ring-buffer records.
 * Lifecycle events are sparse, so one record per event is affordable.
 * Also maintains the shared `targets` set (children inherit monitoring). */
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>
#include "event_maps.h"

struct {
	__uint(type, BPF_MAP_TYPE_RINGBUF);
	__uint(max_entries, DEFAULT_RINGBUF_KB * 1024); /* resized by loader */
} events SEC(".maps");

static __always_inline struct event *reserve(__u32 type)
{
	struct event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);

	if (!e) {
		stat_inc(STAT_RB_DROPPED);
		return NULL;
	}
	e->timestamp = bpf_ktime_get_ns();
	e->event_type = type;
	e->_pad = 0;
	e->value = 0;
	return e;
}

SEC("tp_btf/sched_process_fork")
int BPF_PROG(on_fork, struct task_struct *parent, struct task_struct *child)
{
	__u32 ctgid = BPF_CORE_READ(child, tgid);
	__u32 ctid  = BPF_CORE_READ(child, pid);

	if (ctgid != ctid)              /* a new thread, not a new process */
		return 0;

	__u32 ptgid = BPF_CORE_READ(parent, tgid);

	if (filter_enabled && bpf_map_lookup_elem(&targets, &ptgid)) {
		__u8 one = 1;
		bpf_map_update_elem(&targets, &ctgid, &one, BPF_ANY);
	}
	if (!is_monitored(ptgid))
		return 0;

	struct event *e = reserve(EVT_FORK);
	if (!e)
		return 0;
	__u64 ug = bpf_get_current_uid_gid();
	e->pid = ptgid;                 /* forking process                 */
	e->ppid = BPF_CORE_READ(parent, real_parent, tgid);
	e->uid = (__u32)ug;
	e->gid = ug >> 32;
	e->value = ctgid;               /* child                           */
	BPF_CORE_READ_STR_INTO(&e->comm, parent, comm);
	bpf_ringbuf_submit(e, 0);
	return 0;
}

SEC("tracepoint/sched/sched_process_exec")
int on_exec(void *ctx)
{
	__u64 pt = bpf_get_current_pid_tgid();
	__u32 tgid = pt >> 32;

	if (!is_monitored(tgid))
		return 0;
	struct task_struct *task = (struct task_struct *)bpf_get_current_task();
	struct event *e = reserve(EVT_EXEC);
	if (!e)
		return 0;
	__u64 ug = bpf_get_current_uid_gid();
	e->pid = tgid;
	e->ppid = BPF_CORE_READ(task, real_parent, tgid);
	e->uid = (__u32)ug;
	e->gid = ug >> 32;
	e->value = (__u32)pt;           /* tid that called exec            */
	bpf_get_current_comm(&e->comm, sizeof(e->comm));
	bpf_ringbuf_submit(e, 0);
	return 0;
}

SEC("tracepoint/sched/sched_process_exit")
int on_exit(void *ctx)
{
	__u64 pt = bpf_get_current_pid_tgid();
	__u32 tgid = pt >> 32, tid = (__u32)pt;

	if (tgid != tid)                /* report once, at group leader    */
		return 0;
	if (!is_monitored(tgid))
		return 0;
	struct task_struct *task = (struct task_struct *)bpf_get_current_task();
	struct event *e = reserve(EVT_EXIT);
	if (!e)
		return 0;
	__u64 ug = bpf_get_current_uid_gid();
	e->pid = tgid;
	e->ppid = BPF_CORE_READ(task, real_parent, tgid);
	e->uid = (__u32)ug;
	e->gid = ug >> 32;
	e->value = BPF_CORE_READ(task, exit_code);
	bpf_get_current_comm(&e->comm, sizeof(e->comm));
	bpf_ringbuf_submit(e, 0);
	if (filter_enabled)
		bpf_map_delete_elem(&targets, &tgid);
	return 0;
}

char LICENSE[] SEC("license") = "GPL";
