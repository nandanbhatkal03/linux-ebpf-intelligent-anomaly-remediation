ROOT  := $(abspath $(CURDIR)/..)
BUILD := $(ROOT)/build
CC    ?= gcc
CFLAGS ?= -O2 -g -Wall -Wextra -Wno-unused-parameter
INC   := -I include -I $(ROOT)/ebpf/include -I $(BUILD)/skel
SRCS  := $(wildcard src/*.c)

all: $(BUILD)/ebpf-collector

$(BUILD)/ebpf-collector: $(SRCS) include/collector.h $(wildcard $(BUILD)/skel/*.skel.h)
	@mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(INC) $(SRCS) -o $@ -lbpf -lelf -lz

clean:
	rm -f $(BUILD)/ebpf-collector

.PHONY: all clean
