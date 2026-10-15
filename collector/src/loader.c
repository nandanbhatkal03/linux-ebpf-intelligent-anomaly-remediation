// SPDX-License-Identifier: GPL-2.0
/* Opens, configures, loads and attaches the three eBPF skeletons. */
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <sys/resource.h>
#include <bpf/bpf.h>
#include "collector.h"
#include "syscall_monitor.skel.h"
#include "process_monitor.skel.h"
#include "resource_monitor.skel.h"

static int tracepoint_exists(const char *subsys_event)
{
	char p[256];

	snprintf(p, sizeof(p), "/sys/kernel/tracing/events/%s", subsys_event);
	if (!access(p, F_OK))
		return 1;
	snprintf(p, sizeof(p), "/sys/kernel/debug/tracing/events/%s", subsys_event);
	return !access(p, F_OK);
}

int loader_open(const struct cfg *cfg, struct loader *ld)
{
	struct rlimit rl = { RLIM_INFINITY, RLIM_INFINITY };
	__u32 tgid = getpid();
	int err;

	memset(ld, 0, sizeof(*ld));
	ld->stats_fd = -1;
	ld->ncpu = libbpf_num_possible_cpus();
	setrlimit(RLIMIT_MEMLOCK, &rl);     /* needed on kernels < 5.11 only */

	/* One shared `targets` set: every skeleton reuses this map. */
	ld->targets_fd = bpf_map_create(BPF_MAP_TYPE_HASH, "targets",
					sizeof(__u32), sizeof(__u8), MAX_TARGETS, NULL);
	if (ld->targets_fd < 0)
		return -errno;
	for (int i = 0; i < cfg->npids; i++) {
		__u32 k = cfg->pids[i];
		__u8 one = 1;
		bpf_map_update_elem(ld->targets_fd, &k, &one, BPF_ANY);
	}
	__u8 filt = cfg->npids > 0;

	if (cfg->enable_sys) {
		ld->sys = syscall_monitor_bpf__open();
		if (!ld->sys)
			return -errno;
		ld->sys->rodata->self_tgid = tgid;
		ld->sys->rodata->filter_enabled = filt;
		bpf_map__reuse_fd(ld->sys->maps.targets, ld->targets_fd);
		if ((err = syscall_monitor_bpf__load(ld->sys)))
			return err;
	}
	if (cfg->enable_proc) {
		ld->proc = process_monitor_bpf__open();
		if (!ld->proc)
			return -errno;
		ld->proc->rodata->self_tgid = tgid;
		ld->proc->rodata->filter_enabled = filt;
		bpf_map__reuse_fd(ld->proc->maps.targets, ld->targets_fd);
		bpf_map__set_max_entries(ld->proc->maps.events, (__u32)cfg->ringbuf_kb * 1024);
		if ((err = process_monitor_bpf__load(ld->proc)))
			return err;
	}
	if (cfg->enable_res) {
		ld->res = resource_monitor_bpf__open();
		if (!ld->res)
			return -errno;
		ld->res->rodata->self_tgid = tgid;
		ld->res->rodata->filter_enabled = filt;
		bpf_map__reuse_fd(ld->res->maps.targets, ld->targets_fd);
		ld->page_fault_enabled = tracepoint_exists("exceptions/page_fault_user");
		bpf_program__set_autoload(ld->res->progs.on_page_fault, ld->page_fault_enabled);
		if ((err = resource_monitor_bpf__load(ld->res)))
			return err;
	}
	return 0;
}

int loader_attach(struct loader *ld)
{
	int err;

	/* Run-time accounting of every BPF program (kernel-side overhead). */
	ld->stats_fd = bpf_enable_stats(BPF_STATS_RUN_TIME);
	if (ld->sys && (err = syscall_monitor_bpf__attach(ld->sys)))
		return err;
	if (ld->proc && (err = process_monitor_bpf__attach(ld->proc)))
		return err;
	if (ld->res && (err = resource_monitor_bpf__attach(ld->res)))
		return err;
	return 0;
}

static void prog_row(FILE *f, const char *name, struct bpf_program *p)
{
	struct bpf_prog_info info = {};
	__u32 len = sizeof(info);
	int fd = bpf_program__fd(p);

	if (fd < 0 || bpf_obj_get_info_by_fd(fd, &info, &len))
		return;
	fprintf(f, "%s,%llu,%llu,%.1f\n", name,
		(unsigned long long)info.run_cnt,
		(unsigned long long)info.run_time_ns,
		info.run_cnt ? (double)info.run_time_ns / info.run_cnt : 0.0);
}

int loader_prog_stats(const struct loader *ld, FILE *out)
{
	fprintf(out, "program,run_cnt,run_time_ns,avg_ns_per_run\n");
	if (ld->sys)
		prog_row(out, "on_sys_enter", ld->sys->progs.on_sys_enter);
	if (ld->proc) {
		prog_row(out, "on_fork", ld->proc->progs.on_fork);
		prog_row(out, "on_exec", ld->proc->progs.on_exec);
		prog_row(out, "on_exit", ld->proc->progs.on_exit);
	}
	if (ld->res) {
		prog_row(out, "on_switch", ld->res->progs.on_switch);
		if (ld->page_fault_enabled)
			prog_row(out, "on_page_fault", ld->res->progs.on_page_fault);
	}
	return 0;
}

void loader_close(struct loader *ld)
{
	if (ld->rb)
		ring_buffer__free(ld->rb);
	if (ld->sys)
		syscall_monitor_bpf__destroy(ld->sys);
	if (ld->proc)
		process_monitor_bpf__destroy(ld->proc);
	if (ld->res)
		resource_monitor_bpf__destroy(ld->res);
	if (ld->stats_fd >= 0)
		close(ld->stats_fd);
	if (ld->targets_fd >= 0)
		close(ld->targets_fd);
}

/* Map-fd accessors used by map_flush.c / metrics.c (keeps skeleton headers
 * private to this translation unit). */
int loader_syscall_map_fd(const struct loader *ld)
{
	return ld->sys ? bpf_map__fd(ld->sys->maps.syscall_counts) : -1;
}
int loader_cpu_map_fd(const struct loader *ld)
{
	return ld->res ? bpf_map__fd(ld->res->maps.cpu_stats) : -1;
}
int loader_stats_fd(const struct loader *ld, int which)
{
	if (which == 0 && ld->proc) return bpf_map__fd(ld->proc->maps.stats);
	if (which == 1 && ld->sys)  return bpf_map__fd(ld->sys->maps.stats);
	if (which == 2 && ld->res)  return bpf_map__fd(ld->res->maps.stats);
	return -1;
}
int loader_events_map_fd(const struct loader *ld)
{
	return ld->proc ? bpf_map__fd(ld->proc->maps.events) : -1;
}
