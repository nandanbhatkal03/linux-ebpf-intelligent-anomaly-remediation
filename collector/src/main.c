// SPDX-License-Identifier: GPL-2.0
/* ebpf-collector: loads the eBPF monitors, drains them, writes raw CSV data.
 *
 *   sudo ./build/ebpf-collector -o datasets/raw/local/run1 -w 1000 -d 60
 *
 * Output (all timestamps CLOCK_MONOTONIC ns, identical to bpf_ktime_get_ns):
 *   process_events.csv   fork/exec/exit records (ring buffer)
 *   syscall_windows.csv  per-window syscall counts per (pid, syscall nr)
 *   resource_windows.csv per-window CPU time / switches / page faults per pid
 *   collector_metrics.csv  collector CPU, RSS, event counts, drops (1 row/window)
 *   bpf_prog_stats.csv   in-kernel run count / run time of every BPF program
 *   meta.json            run description (kernel, windows, clocks)
 */
#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include "collector.h"

extern uint64_t g_events_seen;
static volatile sig_atomic_t stop;

static void on_signal(int sig) { (void)sig; stop = 1; }

static int g_verbose;

static int libbpf_print(enum libbpf_print_level lvl, const char *fmt, va_list ap)
{
	return (lvl == LIBBPF_DEBUG && !g_verbose) ? 0 : vfprintf(stderr, fmt, ap);
}

static void usage(const char *p)
{
	fprintf(stderr,
	"Usage: %s [options]\n"
	"  -o, --outdir DIR      output directory (default ./collector_out)\n"
	"  -w, --window-ms N     aggregation window, ms (default 1000)\n"
	"  -d, --duration SEC    stop after SEC seconds (default: until Ctrl-C)\n"
	"  -p, --pid PID         monitor only PID and its descendants (repeatable)\n"
	"  -r, --ringbuf-kb N    process-event ring buffer size (default %d)\n"
	"      --run-id ID       label stored in meta.json\n"
	"      --no-syscalls | --no-process | --no-resource   disable a monitor\n"
	"  -v, --verbose         libbpf debug output\n", p, DEFAULT_RINGBUF_KB);
}

static void mkdirs(const char *path)
{
	char tmp[256];

	snprintf(tmp, sizeof(tmp), "%s", path);
	for (char *p = tmp + 1; *p; p++)
		if (*p == '/') { *p = 0; mkdir(tmp, 0755); *p = '/'; }
	mkdir(tmp, 0755);
}

static FILE *open_csv(const char *dir, const char *name, const char *header)
{
	char path[512];
	FILE *f;

	snprintf(path, sizeof(path), "%s/%s", dir, name);
	f = fopen(path, "w");
	if (!f) {
		fprintf(stderr, "cannot create %s: %s\n", path, strerror(errno));
		exit(1);
	}
	if (header)
		fprintf(f, "%s\n", header);
	return f;
}

static void write_meta(const struct cfg *c, const struct loader *ld,
		       uint64_t t_start, uint64_t t_end, uint64_t rt_start)
{
	struct utsname u;
	char path[512];
	FILE *f;

	uname(&u);
	snprintf(path, sizeof(path), "%s/meta.json", c->outdir);
	if (!(f = fopen(path, "w")))
		return;
	fprintf(f, "{\n  \"run_id\": \"%s\",\n  \"kernel\": \"%s\",\n  \"arch\": \"%s\",\n"
		   "  \"ncpu\": %d,\n  \"window_ms\": %d,\n  \"filter_pids\": %d,\n"
		   "  \"monitors\": {\"process\": %d, \"syscall\": %d, \"resource\": %d},\n"
		   "  \"page_fault_probe\": %d,\n  \"cpu_accounting\": \"%s\",\n  \"ringbuf_kb\": %d,\n"
		   "  \"start_monotonic_ns\": %llu,\n  \"end_monotonic_ns\": %llu,\n"
		   "  \"start_realtime_ns\": %llu\n}\n",
		c->run_id, u.release, u.machine, ld->ncpu, c->window_ms, c->npids,
		c->enable_proc, c->enable_sys, c->enable_res, ld->page_fault_enabled,
		ld->runtime_acct ? "sched_stat_runtime" : "switch_delta", c->ringbuf_kb, (unsigned long long)t_start, (unsigned long long)t_end,
		(unsigned long long)rt_start);
	fclose(f);
}

int main(int argc, char **argv)
{
	struct cfg c = { .window_ms = 1000, .ringbuf_kb = DEFAULT_RINGBUF_KB,
			 .enable_proc = 1, .enable_sys = 1, .enable_res = 1 };
	struct option opts[] = {
		{ "outdir", 1, 0, 'o' }, { "window-ms", 1, 0, 'w' },
		{ "duration", 1, 0, 'd' }, { "pid", 1, 0, 'p' },
		{ "ringbuf-kb", 1, 0, 'r' }, { "run-id", 1, 0, 1000 },
		{ "no-syscalls", 0, 0, 1001 }, { "no-process", 0, 0, 1002 },
		{ "no-resource", 0, 0, 1003 }, { "verbose", 0, 0, 'v' },
		{ "help", 0, 0, 'h' }, { 0 } };
	int o;

	snprintf(c.outdir, sizeof(c.outdir), "collector_out");
	snprintf(c.run_id, sizeof(c.run_id), "run-%ld", (long)time(NULL));
	while ((o = getopt_long(argc, argv, "o:w:d:p:r:vh", opts, NULL)) != -1) {
		switch (o) {
		case 'o': snprintf(c.outdir, sizeof(c.outdir), "%s", optarg); break;
		case 'w': c.window_ms = atoi(optarg); break;
		case 'd': c.duration_s = atoi(optarg); break;
		case 'p': if (c.npids < MAX_CLI_PIDS) c.pids[c.npids++] = atoi(optarg); break;
		case 'r': c.ringbuf_kb = atoi(optarg); break;
		case 'v': c.verbose = 1; break;
		case 1000: snprintf(c.run_id, sizeof(c.run_id), "%s", optarg); break;
		case 1001: c.enable_sys = 0; break;
		case 1002: c.enable_proc = 0; break;
		case 1003: c.enable_res = 0; break;
		default: usage(argv[0]); return o == 'h' ? 0 : 2;
		}
	}
	if (c.window_ms < 10 || c.ringbuf_kb < 64 || (c.ringbuf_kb & (c.ringbuf_kb - 1))) {
		fprintf(stderr, "window-ms must be >= 10; ringbuf-kb a power of two >= 64\n");
		return 2;
	}
	if (geteuid() != 0)
		fprintf(stderr, "warning: not root; loading BPF programs usually needs "
				"CAP_BPF/CAP_PERFMON (run with sudo)\n");

	g_verbose = c.verbose;
	libbpf_set_print(libbpf_print);
	mkdirs(c.outdir);
	signal(SIGINT, on_signal);
	signal(SIGTERM, on_signal);

	struct loader ld;
	struct outputs out = {};
	int err = loader_open(&c, &ld);

	if (err) {
		fprintf(stderr, "failed to open/load BPF programs: %s\n", strerror(-err));
		loader_close(&ld);
		return 1;
	}
	out.proc = open_csv(c.outdir, "process_events.csv",
			    "ts_ns,event,pid,ppid,uid,gid,value,comm");
	out.sys  = open_csv(c.outdir, "syscall_windows.csv",
			    "window_start_ns,window_end_ns,pid,comm,nr,count");
	out.res  = open_csv(c.outdir, "resource_windows.csv",
			    "window_start_ns,window_end_ns,pid,comm,cpu_ns,switches,"
			    "invol_switches,page_faults");
	out.met  = open_csv(c.outdir, "collector_metrics.csv", NULL);
	metrics_header(out.met);

	if ((err = rb_setup(&ld, &out)) || (err = loader_attach(&ld))) {
		fprintf(stderr, "failed to attach: %s\n", strerror(-err));
		loader_close(&ld);
		return 1;
	}

	struct timespec rt;
	clock_gettime(CLOCK_REALTIME, &rt);
	uint64_t realtime0 = (uint64_t)rt.tv_sec * 1000000000ull + rt.tv_nsec;
	uint64_t t0 = now_ns(), win_ns = (uint64_t)c.window_ms * 1000000ull;
	uint64_t win_start = t0, next = t0 + win_ns;

	write_meta(&c, &ld, t0, 0, realtime0);
	fprintf(stderr, "collector running: window=%d ms, outdir=%s, cpus=%d%s\n",
		c.window_ms, c.outdir, ld.ncpu, c.npids ? " (filtered)" : " (all processes)");

	while (!stop) {
		uint64_t now = now_ns();

		if (c.duration_s && now - t0 >= (uint64_t)c.duration_s * 1000000000ull)
			break;
		int wait_ms = next > now ? (int)((next - now) / 1000000ull) + 1 : 0;

		rb_drain(&ld, wait_ms);
		now = now_ns();
		if (now >= next) {
			long rows = flush_syscalls(&ld, out.sys, win_start, now);
			flush_cpu(&ld, out.res, win_start, now);
			metrics_row(&ld, out.met, g_events_seen, rows);
			fflush(out.sys); fflush(out.res); fflush(out.met); fflush(out.proc);
			win_start = now;
			next += win_ns;
			if (next <= now)
				next = now + win_ns;
		}
	}
	/* final drain */
	uint64_t t_end = now_ns();
	rb_drain(&ld, 0);
	long rows = flush_syscalls(&ld, out.sys, win_start, t_end);
	flush_cpu(&ld, out.res, win_start, t_end);
	metrics_row(&ld, out.met, g_events_seen, rows);

	char path[512];
	snprintf(path, sizeof(path), "%s/bpf_prog_stats.csv", c.outdir);
	FILE *ps = fopen(path, "w");
	if (ps) {
		loader_prog_stats(&ld, ps);
		fclose(ps);
	}
	write_meta(&c, &ld, t0, t_end, realtime0);
	fclose(out.proc); fclose(out.sys); fclose(out.res); fclose(out.met);
	fprintf(stderr, "done: %llu process events, outdir=%s\n",
		(unsigned long long)g_events_seen, c.outdir);
	loader_close(&ld);
	return 0;
}
