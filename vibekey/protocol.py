"""AU05 report decoding. Standard HID is the default reporting path.

Vendor framing and TEA constants are documented in the upstream references
listed in THIRD_PARTY.md. No Studio heartbeat or device configuration writes.
"""
import struct

KEY = bytes.fromhex("ca ba a5 ca 6d 8a 2a bc ba 9e 5a ca ca 8b b8 9b")
MASK = 0xffffffff


def tea_block(block, decrypt=False):
    v0, v1 = struct.unpack("<2I", block)
    a, b, c, d = struct.unpack("<4I", KEY)
    delta = 0x9e3779b9
    total = (delta * 32) & MASK if decrypt else 0
    for _ in range(32):
        if decrypt:
            v1 = (v1 - (((v0 << 4) + c) ^ (v0 + total) ^ ((v0 >> 5) + d))) & MASK
            v0 = (v0 - (((v1 << 4) + a) ^ (v1 + total) ^ ((v1 >> 5) + b))) & MASK
            total = (total - delta) & MASK
        else:
            total = (total + delta) & MASK
            v0 = (v0 + (((v1 << 4) + a) ^ (v1 + total) ^ ((v1 >> 5) + b))) & MASK
            v1 = (v1 + (((v0 << 4) + c) ^ (v0 + total) ^ ((v0 >> 5) + d))) & MASK
    return struct.pack("<2I", v0, v1)


def encode_vendor(payload):
    if len(payload) > 64:
        raise ValueError("Payload exceeds 64 bytes")
    plain = payload.ljust(64, b"\0")
    encrypted = b"".join(tea_block(plain[i:i + 8]) for i in range(0, 64, 8))
    return b"\x55" + encrypted[:63]


def decode_vendor(report):
    if len(report) != 64 or report[0] != 0x55:
        return None
    # The final ciphertext block is truncated and cannot be decrypted.
    return b"".join(tea_block(report[i:i + 8], True) for i in range(1, 57, 8))


def vendor_event(report):
    plain = decode_vendor(report)
    if plain is None:
        return None
    if plain[0] & 0x1f == 0x0b and plain[1] == 0x10 and plain[4] < 6:
        return {
            "kind": "control", "control": ("top", "middle", "bottom", "knob", "cw", "ccw")[plain[4]],
            "pressed": plain[3] == 1, "pulse": plain[4] >= 4,
        } if plain[3] in (0, 1) else None
    if plain[:4] == b"\x81\x01\x02\x11":
        voltage, percent = struct.unpack_from("<HH", plain, 4)
        return {"kind": "battery", "millivolts": voltage,
                "percent": percent if percent <= 100 else None,
                "charging": bool(plain[10]) if plain[10] in (0, 1) else None}
    if plain[:4] == b"\x06\x03\x0a\x11":
        return {"kind": "online", "online": bool(plain[4])}
    return None


class StandardDecoder:
    """Return (signature, pressed, pulse) edges; keep reports independent."""
    def __init__(self):
        self.held = {}
        self.keyboard_keys = ()

    def reset(self):
        edges = [(sig, False, False) for sig in self.held.values() if sig]
        self.held.clear()
        self.keyboard_keys = ()
        return edges

    def feed(self, report):
        if not report:
            return []
        rid = report[0]
        signature = None
        pulses = []
        if rid == 3 and len(report) >= 9:
            keys = tuple(sorted(set(k for k in report[3:9] if k)))
            if keys:
                # AU05 can send modifier-only, modifier+key, key-only, empty
                # reports for one physical press. Keep its initial chord until
                # the non-modifier keys change; release ordering must not turn
                # a single press into a second unmodified action.
                signature = (self.held.get(rid) if keys == self.keyboard_keys else
                             "keyboard:%02x:%s" % (
                                 report[1], ",".join("%02x" % k for k in keys)))
            # Modifier-only reports are chord setup/teardown, not controls.
            self.keyboard_keys = keys
        elif rid == 1 and len(report) >= 3:
            usage = int.from_bytes(report[1:3], "little")
            if usage:
                signature = "consumer:%04x" % usage
        elif rid == 2 and len(report) >= 5:
            if report[1]:
                signature = "mouse:%02x" % report[1]
            wheel = struct.unpack("b", report[4:5])[0]
            pulses = [("wheel:+" if wheel > 0 else "wheel:-", True, True)] * abs(wheel)
        else:
            return []
        old = self.held.get(rid)
        edges = []
        if signature != old:
            if old:
                edges.append((old, False, False))
            if signature:
                edges.append((signature, True, False))
            self.held[rid] = signature
        return edges + pulses
