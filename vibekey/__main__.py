import argparse
import json
import os
import shutil
import signal
import sys
import threading
from . import __version__
from .device import discover


def main():
    parser = argparse.ArgumentParser(description="Ulanzi AU05 userspace driver and local web UI")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--simulate", action="store_true", help="No physical device or action execution")
    parser.add_argument("--config", help="Alternate configuration JSON")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--diagnose", action="store_true", help="Read-only host/device diagnostics")
    args = parser.parse_args()
    if args.diagnose:
        print(json.dumps({
            "python": sys.version.split()[0], "session": os.environ.get("XDG_SESSION_TYPE"),
            "devices": discover(), "uinput_writable": os.access("/dev/uinput", os.W_OK),
            "commands": {name: bool(shutil.which(name)) for name in ("parec", "whisper-cli")},
        }, indent=2))
        return
    from .runtime import Runtime
    from .server import Server
    runtime = Runtime(args.config, args.simulate)
    try:
        server = Server(runtime, args.port)
    except OSError as exc:
        runtime.close()
        parser.exit(1, "Cannot start local server: %s\n" % exc)
    stopping = threading.Event()

    def stop(_signum, _frame):
        if not stopping.is_set():
            stopping.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    runtime.start()
    print("VibeKey %s: http://127.0.0.1:%d%s" % (
        __version__, server.server_port, " (simulation)" if args.simulate else ""), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        runtime.close()
        server.server_close()


if __name__ == "__main__":
    main()
