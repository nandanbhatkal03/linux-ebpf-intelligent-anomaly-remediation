// SPDX-License-Identifier: GPL-2.0
/* Collector self-metrics: CPU time, RSS, event/drop counters (Objective 6). */
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <sys/resource.h>
#include <bpf/bpf.h>
#include "collector.h"

int loader_stats_fd(const struct loader *ld, int which);

uint64_t now_ns(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);   /* same clock as bpf_ktime_get_ns */
	return (uint64_t)ts.tv_sec * 1000000000ull + ts.tv_nsec;
}

uint64_t stat_total(int stats_fd, uint32_t idx, int ncpu)
{
	uint64_t *v, sum = 0;

	if (stats_fd < 0)
		return 0;
	v = calloc(ncpu, sizeof(*v));
	if (v && !bpf_map_lookup_elem(stats_fd, &idx, v))
		for (int c = 0; c < ncpu; c++)
			sum += v[c];
	free(v);
	return sum;
}

static long rss_kb(void)
{
	long pages = 0, rss = 0;
	FILE *f = fopen("/proc/self/statm", "r");

	if (f) {
		if (fscanf(f, "%ld %ld", &pages, &rss) != 2)
			rss = 0;
		fclose(f);
	}
	return rss * (sysconf(_SC_PAGESIZE) / 1024);
}

void metrics_header(FILE *f)
{
	fprintf(f, "ts_ns,events_received,ringbuf_dropped,map_failures,"
		   "syscall_rows_flushed,collector_cpu_ms,collector_rss_kb\n");
}

void metrics_row(const struct loader *ld, FILE *f, uint64_t events_seen, long sys_rows)
{
	struct rusage ru;
	uint64_t dropped = 0, fails = 0;
	long cpu_ms;

	getrusage(RUSAGE_SELF, &ru);
	cpu_ms = ru.ru_utime.tv_sec * 1000 + ru.ru_utime.tv_usec / 1000 +
		 ru.ru_stime.tv_sec * 1000 + ru.ru_stime.tv_usec / 1000;
	dropped = stat_total(loader_stats_fd(ld, 0), STAT_RB_DROPPED, ld->ncpu);
	for (int w = 0; w < 3; w++)
		fails += stat_total(loader_stats_fd(ld, w), STAT_MAP_FAIL, ld->ncpu);
	fprintf(f, "%llu,%llu,%llu,%llu,%ld,%ld,%ld\n", (unsigned long long)now_ns(),
		(unsigned long long)events_seen, (unsigned long long)dropped,
		(unsigned long long)fails, sys_rows, cpu_ms, rss_kb());
}
