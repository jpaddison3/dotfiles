#!/usr/bin/env python3
"""Reader end of the process substitution stderr-to-logfile.py splices into a
rewritten command's discard redirect. Usage:

    logfile-sink.py [--stream=err|out|out+err] LABEL

LABEL is the full original command, used to prefix every line so a grep hit is
self-identifying; --stream tags which discarded stream this sink is reading
(default err, which also keeps rewrites from older hook versions working).

Deliberately fork-free and chunk-based: this sits on the producing command's
pipe, so anything slow here becomes backpressure on the command itself (a
shell `date`-per-line version cost ~3ms/line, i.e. minutes for a
`find / 2>/dev/null` flood). Reading chunks rather than lines also survives
what stdout discards can carry that stderr rarely does: binary output (NUL
sniff -> suppress) and no-newline streams like `\r` progress bars (flushed at
MAX_LINE instead of buffering without bound). MAX_WRITE caps one invocation's
total append so a flood can't swamp ~/.logs -- note a capped long-lived
daemon logs its first ~5MB and then nothing.
"""
import os
import sys
import time

LOGDIR = os.path.join(os.path.expanduser("~"), ".logs")
MAX_LINE = 64 * 1024  # flush an unterminated line at this size
MAX_WRITE = 5 * 1024 * 1024  # per-invocation cap on bytes appended


def main():
    args = sys.argv[1:]
    stream = "err"
    if args and args[0].startswith("--stream="):
        stream = args[0][len("--stream="):] or "err"
        args = args[1:]
    label = " ".join(args[0].split()) if args else "unknown command"

    # The sink inherits the caller's stdout, and in a pipeline that is the pipe
    # to the next stage -- holding it open would stall that stage for as long as
    # the sink lives. It has no business writing there anyway. stderr is left
    # alone so the sink's own breakage stays visible rather than silent.
    with open(os.devnull, "w") as devnull:
        os.dup2(devnull.fileno(), 1)

    os.makedirs(LOGDIR, exist_ok=True)
    day = None
    handle = None
    written = 0

    def emit(text):
        nonlocal day, handle, written
        now = time.localtime()
        today = time.strftime("%Y-%m-%d", now)
        if today != day:  # long-lived sinks (daemons) roll over at midnight
            if handle is not None:
                handle.close()
            handle = open(os.path.join(LOGDIR, today + ".log"), "a", buffering=1)
            day = today
        out = "%s [%s] [%s] %s\n" % (
            time.strftime("%Y-%m-%dT%H:%M:%S%z", now), stream, label, text,
        )
        handle.write(out)
        written += len(out)

    buf = b""
    suppressed = False  # stop appending content, but keep draining the pipe
    dropped = 0
    try:
        while True:
            chunk = sys.stdin.buffer.read1(65536)
            if not chunk:
                break
            if suppressed:
                dropped += len(chunk)
                continue
            if b"\x00" in chunk:
                emit("[binary output detected; discarding the rest of this stream]")
                suppressed = True
                dropped += len(buf) + len(chunk)
                buf = b""
                continue
            parts = (buf + chunk).split(b"\n")
            buf = parts.pop()
            for raw in parts:
                emit(raw.decode("utf-8", "replace").rstrip("\r"))
                if written >= MAX_WRITE:
                    break
            if not suppressed and written < MAX_WRITE and len(buf) > MAX_LINE:
                emit(buf.decode("utf-8", "replace") + " [line truncated]")
                buf = b""
            if written >= MAX_WRITE:
                emit("[output cap reached; discarding the rest of this stream]")
                suppressed = True
                dropped += len(buf)
                buf = b""
        if buf and not suppressed:
            emit(buf.decode("utf-8", "replace").rstrip("\r"))
        if dropped:
            emit("[%d bytes discarded]" % dropped)
    finally:
        if handle is not None:
            handle.close()


if __name__ == "__main__":
    main()
