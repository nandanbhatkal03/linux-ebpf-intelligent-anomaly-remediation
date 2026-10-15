#!/usr/bin/env bash
# Stops every running collector gracefully (SIGINT lets it write meta.json + prog stats).
pkill -INT -x ebpf-collector && echo "collector stopped" || echo "no collector running"
