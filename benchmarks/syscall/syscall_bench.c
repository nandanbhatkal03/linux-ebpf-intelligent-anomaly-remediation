// SPDX-License-Identifier: GPL-2.0
/* Micro-benchmarks for monitoring overhead.
 *   syscall_bench sys N   -> mean ns per getppid() syscall (worst case for a sys_enter probe)
 *   syscall_bench cpu N   -> seconds for N million integer ops (CPU-bound, ~no syscalls)
 *   syscall_bench io  N   -> mean ns per 4 KiB read() from /dev/zero (syscall + copy) */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

static double now(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return t.tv_sec + t.tv_nsec * 1e-9;
}

int main(int argc, char **argv)
{
	if (argc < 3) {
		fprintf(stderr, "usage: %s sys|cpu|io N\n", argv[0]);
		return 2;
	}
	long n = atol(argv[2]);
	double t0 = now();

	if (!strcmp(argv[1], "sys")) {
		for (long i = 0; i < n; i++)
			syscall(SYS_getppid);
		printf("%.2f\n", (now() - t0) / n * 1e9);
	} else if (!strcmp(argv[1], "io")) {
		char buf[4096];
		int fd = open("/dev/zero", O_RDONLY);
		for (long i = 0; i < n; i++)
			if (read(fd, buf, sizeof(buf)) < 0)
				return 1;
		printf("%.2f\n", (now() - t0) / n * 1e9);
	} else {
		volatile unsigned long x = 1;
		for (long i = 0; i < n * 1000000L; i++)
			x = x * 6364136223846793005UL + 1442695040888963407UL;
		printf("%.4f\n", now() - t0);
	}
	return 0;
}
