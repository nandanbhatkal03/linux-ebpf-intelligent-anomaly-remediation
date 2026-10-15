/* SPDX-License-Identifier: GPL-2.0 */
/* Compile-time limits shared by kernel and user-space code. */
#ifndef CONFIG_H
#define CONFIG_H

#define TASK_COMM_LEN      16
#define MAX_TARGETS        8192     /* monitored tgid set (when filtering) */
#define MAX_SYSCALL_NR     512      /* x86_64 uses < 460; aarch64 < 450   */
#define SYSCALL_MAP_SIZE   65536    /* (tgid, nr) pairs live per window    */
#define CPU_MAP_SIZE       16384    /* tgids with CPU accounting           */
#define DEFAULT_RINGBUF_KB 4096     /* process-event ring buffer           */

#endif /* CONFIG_H */
