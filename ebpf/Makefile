# Builds the three eBPF objects and their libbpf skeletons into ../build/.
ROOT     := $(abspath $(CURDIR)/..)
BUILD    := $(ROOT)/build
CLANG    ?= clang
# Ubuntu's /usr/sbin/bpftool is a wrapper that fails on kernels without a matching
# linux-tools package (WSL, cloud kernels). Prefer a real binary that actually runs.
BPFTOOL  ?= $(shell for b in $$(ls /usr/lib/linux-tools/*/bpftool 2>/dev/null) $$(command -v bpftool); do $$b version >/dev/null 2>&1 && { echo $$b; break; }; done)
ARCH     := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')
VMLINUX  := headers/vmlinux.h
PROGS    := syscall_monitor process_monitor resource_monitor
SKELS    := $(PROGS:%=$(BUILD)/skel/%.skel.h)

CFLAGS_BPF := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) -Wall \
              -I headers -I include -I maps -I /usr/include/$(shell uname -m)-linux-gnu

all: $(SKELS)

$(VMLINUX):
	@test -r /sys/kernel/btf/vmlinux || { echo "kernel lacks BTF (CONFIG_DEBUG_INFO_BTF)"; exit 1; }
	@test -n "$(BPFTOOL)" || { echo "bpftool not found (install linux-tools-generic)"; exit 1; }
	$(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

$(BUILD)/ebpf/%.bpf.o: programs/%.bpf.c $(VMLINUX) include/*.h maps/*.h
	@mkdir -p $(BUILD)/ebpf
	$(CLANG) $(CFLAGS_BPF) -c $< -o $@

$(BUILD)/skel/%.skel.h: $(BUILD)/ebpf/%.bpf.o
	@mkdir -p $(BUILD)/skel
	$(BPFTOOL) gen skeleton $< > $@

.SECONDARY:

clean:
	rm -rf $(BUILD)/ebpf $(BUILD)/skel $(VMLINUX)

.PHONY: all clean
