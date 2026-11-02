import fcntl
import os
import select
from pathlib import Path

from .protocol import StandardDecoder, vendor_event

VID, PID = "fff1", "00dd"
EVIOCGRAB = 0x40044590


def _read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def usb_parent(path):
    for parent in (path,) + tuple(path.parents):
        if _read(parent / "idVendor").lower() == VID and _read(parent / "idProduct").lower() == PID:
            return parent
    return None


def discover(sys_root="/sys", dev_root="/dev"):
    root = Path(sys_root)
    devices = {}
    for node in sorted((root / "class/hidraw").glob("hidraw*")):
        resolved = node.resolve()
        usb = usb_parent(resolved)
        if usb is None:
            continue
        key = str(usb)
        entry = devices.setdefault(key, {
            "id": usb.name, "serial": _read(usb / "serial"),
            "product": _read(usb / "product") or "AU05",
            "hidraw": [], "events": [],
        })
        interface = next((_read(p / "bInterfaceNumber") for p in resolved.parents
                          if (p / "bInterfaceNumber").exists()), "")
        entry["hidraw"].append({"path": str(Path(dev_root) / node.name), "interface": interface})
    for node in sorted((root / "class/input").glob("event*")):
        usb = usb_parent(node.resolve())
        if usb is not None and str(usb) in devices:
            devices[str(usb)]["events"].append(str(Path(dev_root) / "input" / node.name))
    return list(devices.values())


class Device:
    def __init__(self, raw_event, control_event, status_event):
        self.raw_event = raw_event
        self.control_event = control_event
        self.status_event = status_event
        self.raw = {}
        self.evdev = []
        self.decoder = StandardDecoder()
        self.selected = None
        self.input_mode = "standard"

    def connect(self, candidates, settings):
        if settings.get("serial"):
            candidates = [d for d in candidates if d["serial"] == settings["serial"]]
        if settings.get("usb_path"):
            candidates = [d for d in candidates if d["id"] == settings["usb_path"]]
        if not candidates:
            raise OSError("No matching AU05 connected")
        if len(candidates) != 1:
            raise OSError("Multiple AU05 devices found; choose serial or USB path")
        device = candidates[0]
        self.close()
        try:
            interfaces = {item["interface"]: item for item in device["hidraw"]}
            if not {"02", "03"}.issubset(interfaces):
                raise OSError("Expected AU05 HID interfaces 02 and 03")
            for interface in ("02", "03"):
                fd = os.open(interfaces[interface]["path"], os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                self.raw[fd] = interface
            if not device["events"]:
                raise OSError("No AU05 evdev siblings; refusing ungrabbed actions")
            # Any failure rolls back every previously acquired grab.
            for path in device["events"]:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                self.evdev.append(fd)
                fcntl.ioctl(fd, EVIOCGRAB, 1)
            self.selected = device
            self.input_mode = settings.get("input_mode", "standard")
        except BaseException:
            self.close()
            raise

    def poll(self, timeout=0):
        if not self.raw:
            return
        ready, _, _ = select.select(list(self.raw) + self.evdev, [], [], timeout)
        for fd in ready:
            while True:
                try:
                    data = os.read(fd, 4096 if fd in self.evdev else 64)
                except BlockingIOError:
                    break
                if not data:
                    raise OSError("Device disconnected")
                if fd in self.evdev:
                    continue  # Drain exclusively grabbed kernel reports.
                if self.raw[fd] == "02":
                    if self.input_mode == "standard":
                        for signature, pressed, pulse in self.decoder.feed(data):
                            self.raw_event(signature, pressed, pulse)
                else:
                    event = vendor_event(data)
                    if event:
                        if event["kind"] == "control":
                            if self.input_mode == "vendor" and (not event["pulse"] or event["pressed"]):
                                self.control_event(event["control"], event["pressed"], event["pulse"])
                        else:
                            self.status_event(event)

    def close(self):
        # Runtime cancels held gestures and actions separately on disconnect.
        for fd in self.evdev:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
            os.close(fd)
        for fd in self.raw:
            os.close(fd)
        self.raw.clear()
        self.evdev.clear()
        self.decoder.reset()
        self.selected = None
