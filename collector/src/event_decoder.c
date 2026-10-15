// SPDX-License-Identifier: GPL-2.0
/* Decodes ring-buffer records into process_events.csv. */
#include <ctype.h>
#include <string.h>
#include "collector.h"

uint64_t g_events_seen;

void sanitize_comm(const char *in, char *out, size_t n)
{
	size_t i = 0;

	for (; i + 1 < n && in[i]; i++)
		out[i] = (isalnum((unsigned char)in[i]) || strchr("._-+:", in[i])) ? in[i] : '_';
	out[i] = 0;
}

int decoder_handle_event(void *ctx, void *data, size_t size)
{
	static const char *names[] = { "?", "fork", "exec", "exit" };
	const struct event *e = data;
	struct outputs *out = ctx;
	char comm[TASK_COMM_LEN + 1];

	if (size < sizeof(*e) || !out->proc)
		return 0;
	sanitize_comm(e->comm, comm, sizeof(comm));
	fprintf(out->proc, "%llu,%s,%u,%u,%u,%u,%llu,%s\n",
		(unsigned long long)e->timestamp,
		e->event_type < 4 ? names[e->event_type] : "?",
		e->pid, e->ppid, e->uid, e->gid,
		(unsigned long long)e->value, comm);
	g_events_seen++;
	return 0;
}
