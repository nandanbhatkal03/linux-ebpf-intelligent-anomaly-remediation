/* SPDX-License-Identifier: GPL-2.0 */
/* Maps and helpers common to every monitor. Each .bpf.c gets its own copy of
 * `targets`; the collector makes them one shared map with bpf_map__reuse_fd(). */
#ifndef EVENT_MAPS_H
#define EVENT_MAPS_H

#include "event_types.h"

struct {
	__uint(type, BPF_MAP_TYPE_HASH);
	__uint(max_entries, MAX_TARGETS);
	__type(key, __u32);
	__type(value, __u8);
} targets SEC(".maps");

struct {
	__uint(type, BPF_MAP_TYPE_PERCPU_ARRAY);
	__uint(max_entries, STAT_MAX);
	__type(key, __u32);
	__type(value, __u64);
} stats SEC(".maps");

const volatile __u32 self_tgid = 0;       /* collector itself: never traced */
const volatile __u8  filter_enabled = 0;  /* 0 = trace everything else      */

static __always_inline void stat_inc(__u32 idx)
{
	__u64 *v = bpf_map_lookup_elem(&stats, &idx);
	if (v)
		(*v)++;
}

static __always_inline int is_monitored(__u32 tgid)
{
	if (tgid == 0 || tgid == self_tgid)
		return 0;
	if (!filter_enabled)
		return 1;
	return bpf_map_lookup_elem(&targets, &tgid) != NULL;
}

#endif /* EVENT_MAPS_H */
