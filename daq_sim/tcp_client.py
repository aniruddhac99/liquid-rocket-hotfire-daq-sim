"""Small validation client for the full-mode TCP protocol; not a LabVIEW replacement."""
from __future__ import annotations
import argparse
import socket
import numpy as np

try:
    from .core import from_raw_volts
    from .protocol import recv_frame, ProtocolError
except ImportError:
    from core import from_raw_volts
    from protocol import recv_frame, ProtocolError


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=5000)
    p.add_argument("--frames", type=int, default=10)
    args = p.parse_args(argv)
    with socket.create_connection(("127.0.0.1", args.port), timeout=5) as sock:
        sock.settimeout(5)
        for _ in range(args.frames):
            try:
                header, arrays = recv_frame(sock)
            except EOFError:
                print("TCP disconnected (expected only for --scenario disconnect)")
                break
            except ProtocolError as e:
                print(f"REJECTED invalid frame: {e}")
                break
            pressure = from_raw_volts(arrays["slow_raw_v"])[:, 0]
            freqs = np.fft.rfftfreq(len(arrays["fast_signal"]), d=1 / 50_000)
            magnitude = np.abs(np.fft.rfft(arrays["fast_signal"][:, 0].astype(np.float64)))
            peak = float(freqs[1 + np.argmax(magnitude[1:])])
            print(f"frame={header['sequence']:03d} t0={header['t0_s']:.1f}s "
                  f"state={header['state']:<8} pressure={pressure[0]:.2f}sim_bar "
                  f"fft={peak:g}Hz fault={header['fault']} "
                  f"abort={header['abort_latched']} reason={header['abort_reason']}")


if __name__ == "__main__":
    main()
