// SPDX-License-Identifier: GPL-2.0
#include <errno.h>
#include <poll.h>
#include "collector.h"

int  loader_events_map_fd(const struct loader *ld);
int  decoder_handle_event(void *ctx, void *data, size_t size);
extern uint64_t g_events_seen;

int rb_setup(struct loader *ld, struct outputs *out)
{
	int fd = loader_events_map_fd(ld);

	if (fd < 0)
		return 0;               /* process monitor disabled */
	ld->rb = ring_buffer__new(fd, decoder_handle_event, out, NULL);
	return ld->rb ? 0 : -errno;
}

/* Waits up to timeout_ms for events. Returns <0 on EINTR (caller checks stop). */
int rb_drain(struct loader *ld, int timeout_ms)
{
	if (!ld->rb)
		return poll(NULL, 0, timeout_ms);
	return ring_buffer__poll(ld->rb, timeout_ms);
}
