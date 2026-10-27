"""TCP synthetic DAQ simulator.

Default 'legacy' mode preserves the original 16-byte ASCII pressure stream
for the existing LabVIEW TCP_Acquisition.vi. 'full' adds 75 analog channels,
30 DI, 30 DO, 2 AO, virtual feedback and repeatable fault scenarios.

Only supports localhost: this is NOT a physical test-stand control server.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import time
import numpy as np

try:  # supports both `python -m daq_sim.tcp_server` and direct script execution
    from .core import Simulator, SCENARIOS, FRAME_SECONDS
    from .protocol import encode_frame
except ImportError:
    from core import Simulator, SCENARIOS, FRAME_SECONDS
    from protocol import encode_frame


def serve_legacy(conn: socket.socket, seed: int, frames: int) -> None:
    rng = np.random.default_rng(seed)
    i = 0
    next_tick = time.monotonic()
    while frames == 0 or i < frames:
        pressure = 2.1 + rng.normal(0, 0.05)
        # Protocol preserved exactly: 16 ASCII bytes, no newline or header.
        conn.sendall(f"{pressure:016.6f}".encode("ascii"))
        if i < 5 or i % 10 == 0:
            print(f"Pressure: {pressure:.3f} bar", flush=True)
        i += 1
        next_tick += 0.1
        time.sleep(max(0.0, next_tick - time.monotonic()))


def serve_full(conn: socket.socket, scenario: str, seed: int,
               fault_frame: int, frames: int, record_dir: Path | None) -> None:
    sim = Simulator(scenario=scenario, seed=seed, fault_frame=fault_frame)
    next_tick = time.monotonic()
    while frames == 0 or sim.sequence < frames:
        # 'disconnect' emulates an unexpected loss of signal before the fault frame.
        if scenario == "disconnect" and sim.sequence == fault_frame:
            print("Injecting deliberate TCP disconnect", flush=True)
            break
        frame = sim.next_frame()
        packet = bytearray(encode_frame(frame))
        if scenario == "corrupt_frame" and frame.sequence == fault_frame:
            packet[-1] ^= 1  # deliberately incorrect CRC for receiver rejection test
        if scenario == "fragmented_frame" and frame.sequence == fault_frame:
            for offset in range(0, len(packet), 1024):
                conn.sendall(packet[offset:offset + 1024])
        else:
            conn.sendall(packet)
        if record_dir is not None:
            record_dir.mkdir(parents=True, exist_ok=True)
            metadata = {"sequence": frame.sequence, "t0_s": frame.t0_s,
                        "state": frame.state, "fault": frame.fault,
                        "abort_latched": frame.abort_latched,
                        "abort_reason": frame.abort_reason}
            np.savez_compressed(record_dir / f"frame_{frame.sequence:06d}.npz",
                                metadata=json.dumps(metadata), **frame.arrays)
        if frame.sequence < 5 or frame.sequence % 10 == 0 or frame.fault != "none":
            print(f"frame={frame.sequence} state={frame.state} fault={frame.fault} "
                  f"abort={frame.abort_latched} reason={frame.abort_reason}", flush=True)
        next_tick += FRAME_SECONDS
        now = time.monotonic()
        if now - next_tick > FRAME_SECONDS:
            print("WARNING: simulated producer missed nominal TCP pacing deadline", flush=True)
            next_tick = now
        time.sleep(max(0.0, next_tick - time.monotonic()))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Synthetic localhost DAQ stream (no hardware)")
    p.add_argument("--mode", choices=("legacy", "full"), default="legacy")
    p.add_argument("--scenario", choices=SCENARIOS, default="nominal")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--fault-frame", type=int, default=8)
    p.add_argument("--frames", type=int, default=0,
                   help="Number of frames; 0 = until interrupted")
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--record-dir", type=Path,
                   help="Optional per-frame NPZ reference capture (full mode)")
    args = p.parse_args(argv)
    if args.frames < 0 or args.fault_frame < 0:
        p.error("--frames and --fault-frame must be >= 0")
    if args.mode == "legacy" and (args.scenario != "nominal" or args.record_dir):
        p.error("Scenarios and recording require --mode full")
    if args.scenario == "disconnect" and args.fault_frame == 0:
        p.error("--fault-frame must be > 0 for a disconnect test")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", args.port))
        server.listen(1)
        print(f"DAQ simulator listening on 127.0.0.1:{args.port} "
              f"mode={args.mode} scenario={args.scenario}", flush=True)
        try:
            while True:
                conn, addr = server.accept()
                print(f"LabVIEW/test client connected: {addr}", flush=True)
                try:
                    with conn:
                        if args.mode == "legacy":
                            serve_legacy(conn, args.seed, args.frames)
                        else:
                            serve_full(conn, args.scenario, args.seed, args.fault_frame,
                                       args.frames, args.record_dir)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    print("Client disconnected", flush=True)
                if args.frames or args.scenario == "disconnect":
                    break
        except KeyboardInterrupt:
            print("Stopped", flush=True)


if __name__ == "__main__":
    main()
