"""GTK3 clipboard owner and voice-result window, isolated from the HTTP server."""
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path


def socket_path():
    base = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp/vibekey-%d" % os.getuid()))
    directory = base / "vibekey"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.stat().st_uid != os.getuid():
        raise PermissionError("Unsafe helper runtime directory")
    os.chmod(str(directory), 0o700)
    return directory / "text.sock"


class TextClient:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()

    def send(self, text, show=True):
        with self.lock:
            path = str(socket_path())
            for attempt in range(30):
                try:
                    with socket.socket(socket.AF_UNIX) as connection:
                        connection.settimeout(5)
                        connection.connect(path)
                        connection.sendall((json.dumps({"text": text, "show": show}) + "\n").encode("utf-8"))
                        reply = connection.recv(1024)
                        if not reply.startswith(b"OK"):
                            raise RuntimeError("GTK helper refused text")
                        return
                except (FileNotFoundError, ConnectionRefusedError):
                    if attempt == 0:
                        self.process = subprocess.Popen(
                            [sys.executable, "-m", "vibekey.text_helper"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                    if self.process and self.process.poll() is not None:
                        raise RuntimeError("GTK3 helper unavailable; check python3-gi and desktop session")
                    time.sleep(0.1)
            raise RuntimeError("GTK3 helper did not start")

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


def main():
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    path = str(socket_path())
    # A lock avoids unlinking a live helper's socket on concurrent startup.
    import fcntl
    lock = open(path + ".lock", "a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX)
    server.bind(path)
    os.chmod(path, 0o600)
    server.listen(4)
    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    window = Gtk.Window(title="VibeKey · 语音结果")
    window.set_default_size(520, 250)
    window.connect("delete-event", lambda w, e: w.hide() or True)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_border_width(16)
    window.add(box)
    box.pack_start(Gtk.Label(label="文本已复制。请回到目标应用粘贴。"), False, False, 0)
    view = Gtk.TextView()
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    scroll = Gtk.ScrolledWindow()
    scroll.add(view)
    box.pack_start(scroll, True, True, 0)
    copy_button = Gtk.Button(label="复制编辑后的文本")
    box.pack_start(copy_button, False, False, 0)

    def copy_text(_button):
        buf = view.get_buffer()
        clipboard.set_text(buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True), -1)
    copy_button.connect("clicked", copy_text)

    def deliver(request, complete):
        try:
            text = request["text"]
            clipboard.set_text(text, -1)
            view.get_buffer().set_text(text)
            if request.get("show", True):
                window.show_all()
                window.present()
        finally:
            complete.set()
        return False

    def accept():
        while True:
            connection, _ = server.accept()
            with connection:
                connection.settimeout(5)
                try:
                    data = bytearray()
                    while b"\n" not in data and len(data) <= 1048576:
                        chunk = connection.recv(8192)
                        if not chunk:
                            break
                        data.extend(chunk)
                    if len(data) > 1048576:
                        raise ValueError("Text too large")
                    request = json.loads(bytes(data).decode("utf-8"))
                    if not isinstance(request.get("text"), str):
                        raise ValueError("Invalid text")
                    complete = threading.Event()
                    GLib.idle_add(deliver, request, complete)
                    connection.sendall(b"OK\n" if complete.wait(4) else b"ERROR\n")
                except (OSError, ValueError, KeyError):
                    pass
    threading.Thread(target=accept, daemon=True).start()
    try:
        Gtk.main()
    finally:
        server.close()
        if os.path.exists(path):
            os.unlink(path)


if __name__ == "__main__":
    main()
