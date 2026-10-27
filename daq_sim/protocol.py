"""Versioned, length-prefixed TCP binary frame protocol for the full simulator.

Wire format: uint32 BE packet-length, uint32 BE JSON-length, JSON UTF-8
header, then contiguous little-endian arrays in header fields order.
"""
from __future__ import annotations
import json
import socket
import struct
import zlib
import numpy as np
try:
    from .core import Frame, FRAME_SECONDS, SLOW_RATE_HZ, FAST_RATE_HZ, DIGITAL_RATE_HZ, SLOW_CATALOG, FAST_NAMES
except ImportError:  # direct script execution
    from core import Frame, FRAME_SECONDS, SLOW_RATE_HZ, FAST_RATE_HZ, DIGITAL_RATE_HZ, SLOW_CATALOG, FAST_NAMES

MAX_FRAME_BYTES = 2_000_000
MAX_HEADER_BYTES = 64_000
FIELD_ORDER = ("slow_raw_v", "fast_signal", "di", "do", "ao_v", "valve_feedback")


class ProtocolError(ValueError):
    pass


def encode_frame(frame: Frame) -> bytes:
    arrays = [np.ascontiguousarray(frame.arrays[k]) for k in FIELD_ORDER]
    payload = b"".join(array.tobytes(order="C") for array in arrays)
    meta = {"protocol_version": 1, "sequence": frame.sequence, "t0_s": frame.t0_s,
            "duration_s": FRAME_SECONDS, "clock": "synthetic_sample_index",
            "state": frame.state, "fault": frame.fault,
            "abort_latched": frame.abort_latched, "abort_reason": frame.abort_reason,
            "rates_hz": {"slow_raw_v": SLOW_RATE_HZ, "fast_signal": FAST_RATE_HZ,
                         "di": DIGITAL_RATE_HZ, "do": DIGITAL_RATE_HZ,
                         "ao_v": DIGITAL_RATE_HZ},
            "slow_catalog": SLOW_CATALOG, "fast_channel_names": FAST_NAMES,
            "fields": [{"name": k, "dtype": a.dtype.str, "shape": list(a.shape)}
                       for k, a in zip(FIELD_ORDER, arrays)],
            "payload_crc32": zlib.crc32(payload)}
    header = json.dumps(meta, separators=(",", ":"), allow_nan=False).encode("utf-8")
    body = struct.pack(">I", len(header)) + header + payload
    if len(header) > MAX_HEADER_BYTES or len(body) > MAX_FRAME_BYTES:
        raise ProtocolError("Encoded frame exceeds maximum size")
    return struct.pack(">I", len(body)) + body


def decode_frame(packet: bytes) -> tuple[dict, dict[str, np.ndarray]]:
    if len(packet) < 8:
        raise ProtocolError("Short packet")
    body_size = struct.unpack_from(">I", packet)[0]
    if body_size > MAX_FRAME_BYTES or body_size < 4 or len(packet) != body_size + 4:
        raise ProtocolError("Invalid packet size")
    header_size = struct.unpack_from(">I", packet, 4)[0]
    if header_size > MAX_HEADER_BYTES or header_size > body_size - 4:
        raise ProtocolError("Invalid header size")
    try:
        meta = json.loads(packet[8:8 + header_size].decode("utf-8"))
    except (ValueError, UnicodeError) as e:
        raise ProtocolError("Invalid JSON header") from e
    if meta.get("protocol_version") != 1:
        raise ProtocolError("Unsupported version")
    data = memoryview(packet)[8 + header_size:]
    if zlib.crc32(data) != meta.get("payload_crc32"):
        raise ProtocolError("CRC mismatch")
    fields = meta.get("fields", [])
    if not isinstance(fields, list) or [f.get("name") for f in fields if isinstance(f, dict)] != list(FIELD_ORDER):
        raise ProtocolError("Unexpected field inventory")
    result = {}
    offset = 0
    expected_shapes = ((100, 50), (5000, 25), (10, 30), (10, 30), (10, 2), (2,))
    expected_types = ("<f4", "<f4", "|u1", "|u1", "<f4", "<f4")
    for field, shape, typ in zip(fields, expected_shapes, expected_types):
        try:
            dtype = np.dtype(field["dtype"])
            given_shape = tuple(field["shape"])
        except (KeyError, ValueError, TypeError) as e:
            raise ProtocolError("Invalid field metadata") from e
        if given_shape != shape or dtype.str != typ:
            raise ProtocolError("Unexpected field shape or dtype")
        count = int(np.prod(shape))
        nbytes = count * dtype.itemsize
        if offset + nbytes > len(data):
            raise ProtocolError("Truncated payload")
        result[field["name"]] = np.frombuffer(data[offset:offset + nbytes], dtype=dtype).copy().reshape(shape)
        offset += nbytes
    if offset != len(data):
        raise ProtocolError("Trailing bytes")
    return meta, result


class FrameDecoder:
    """Reassembles arbitrarily chunked/coalesced TCP reads."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> list[tuple[dict, dict[str, np.ndarray]]]:
        self.buffer.extend(chunk)
        frames = []
        while len(self.buffer) >= 4:
            n = struct.unpack_from(">I", self.buffer, 0)[0]
            if not 4 <= n <= MAX_FRAME_BYTES:
                self.buffer.clear()
                raise ProtocolError("Out-of-range frame length")
            if len(self.buffer) < n + 4:
                break
            raw = bytes(self.buffer[:n + 4])
            del self.buffer[:n + 4]
            frames.append(decode_frame(raw))
        return frames


def recv_exact(sock: socket.socket, size: int) -> bytes:
    parts = []
    received = 0
    while received < size:
        chunk = sock.recv(size - received)
        if not chunk:
            raise EOFError(f"Disconnected after {received}/{size} bytes")
        parts.append(chunk)
        received += len(chunk)
    return b"".join(parts)


def recv_frame(sock: socket.socket) -> tuple[dict, dict[str, np.ndarray]]:
    prefix = recv_exact(sock, 4)
    length = struct.unpack(">I", prefix)[0]
    if not 4 <= length <= MAX_FRAME_BYTES:
        raise ProtocolError("Out-of-range frame length")
    return decode_frame(prefix + recv_exact(sock, length))
