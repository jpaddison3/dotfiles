#!/usr/bin/env python3
"""Reader end of the process substitution stderr-to-logfile.py splices into a
rewritten command's stderr redirect. argv[1] is the full original command, used
to label every line so a grep hit is self-identifying.

Deliberately fork-free per line: this sits on the producing command's stderr
pipe, so anything slow here becomes backpressure on the command itself (a
shell `date`-per-line version cost ~3ms/line, i.e. minutes for a
`find / 2>/dev/null` flood).
"""
import os
import sys
import time

LOGDIR = os.path.join(os.path.expanduser("~"), ".logs")


def main():
    label = " ".join(sys.argv[1].split()) if len(sys.argv) > 1 else "unknown command"
    # The sink inherits the caller's stdout, and in a pipeline that is the pipe
    # to the next stage -- holding it open would stall that stage for as long as
    # the sink lives. It has no business writing there anyway. stderr is left
    # alone so the sink's own breakage stays visible rather than silent.
    with open(os.devnull, "w") as devnull:
        os.dup2(devnull.fileno(), 1)

    os.makedirs(LOGDIR, exist_ok=True)
    day = None
    handle = None
    try:
        for raw in sys.stdin.buffer:
            now = time.localtime()
            today = time.strftime("%Y-%m-%d", now)
            if today != day:  # long-lived sinks (daemons) roll over at midnight
                if handle is not None:
                    handle.close()
                handle = open(os.path.join(LOGDIR, today + ".log"), "a", buffering=1)
                day = today
            line = raw.decode("utf-8", "replace").rstrip("\n")
            handle.write(
                "%s [%s] %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S%z", now), label, line)
            )
    finally:
        if handle is not None:
            handle.close()


if __name__ == "__main__":
    main()
