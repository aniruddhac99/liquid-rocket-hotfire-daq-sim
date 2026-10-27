"""Deterministic, synthetic DAQ frames for software testing ONLY.

Nothing in this module interfaces with DAQ hardware or implements a physical engine.
All thresholds, commands, and states are arbitrary software test fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

SLOW_RATE_HZ = 1_000
FAST_RATE_HZ = 50_000
DIGITAL_RATE_HZ = 100
FRAME_SECONDS = 0.1
SLOW_SAMPLES = 100
FAST_SAMPLES = 5_000
DIGITAL_SAMPLES = 10
PRESSURE_LIMIT = 3.0  # synthetic unit, chosen to match the LabVIEW pressure demo
SCENARIOS = ("nominal", "overpressure", "secondary_overpressure", "sensor_dropout",
             "estop", "vibration", "disconnect", "corrupt_frame", "fragmented_frame")


def channel_catalog() -> list[dict]:
    """Exactly 50 slow analog channels with reversible linear calibration."""
    groups = (("pressure", 16, "sim_bar", 0.0, 5.0),
              ("temperature", 14, "sim_deg", 0.0, 100.0),
              ("flow", 12, "sim_flow", 0.0, 5.0),
              ("load", 8, "sim_load", 0.0, 10.0))
    return [{"name": f"{name}_{i:02d}", "unit": unit,
             "eu_min": lo, "eu_max": hi}
            for name, count, unit, lo, hi in groups
            for i in range(1, count + 1)]


SLOW_CATALOG = channel_catalog()
SLOW_MIN = np.array([c["eu_min"] for c in SLOW_CATALOG], dtype=np.float32)
SLOW_MAX = np.array([c["eu_max"] for c in SLOW_CATALOG], dtype=np.float32)
FAST_NAMES = [f"dynamic_pressure_{i:02d}" for i in range(1, 14)] + [f"vibration_{i:02d}" for i in range(1, 13)]


def to_raw_volts(engineering: np.ndarray) -> np.ndarray:
    return (10.0 * (np.asarray(engineering, dtype=np.float32) - SLOW_MIN) / (SLOW_MAX - SLOW_MIN)).astype("<f4")


def from_raw_volts(raw: np.ndarray) -> np.ndarray:
    return (SLOW_MIN + np.asarray(raw, dtype=np.float32) * (SLOW_MAX - SLOW_MIN) / 10.0).astype("<f4")


@dataclass
class Frame:
    sequence: int
    t0_s: float
    state: str
    fault: str
    abort_latched: bool
    abort_reason: str | None
    arrays: dict[str, np.ndarray]


class Simulator:
    """A repeatable, nonphysical telemetry producer with software-only states."""

    def __init__(self, scenario: str = "nominal", seed: int = 42, fault_frame: int = 8):
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario {scenario!r}; expected {SCENARIOS}")
        if fault_frame < 0:
            raise ValueError("fault_frame must be >= 0")
        self.scenario = scenario
        self.rng = np.random.default_rng(seed)
        self.fault_frame = fault_frame
        self.sequence = 0
        self.abort_latched = False
        self.abort_reason: str | None = None
        self.valve_feedback = np.zeros(2, dtype=np.float64)

    def _state(self, sequence: int) -> str:
        if self.abort_latched:
            return "ABORT"
        if sequence < 2:
            return "PRECHECK"
        if sequence < 7:
            return "START"
        if sequence < 18:
            return "HOLD"
        return "SHUTDOWN"

    def next_frame(self) -> Frame:
        seq = self.sequence
        self.sequence += 1
        t0 = seq * FRAME_SECONDS  # sample-index time; NOT synchronized wall-clock time
        fault = self.scenario if seq == self.fault_frame else "none"

        slow = np.empty((SLOW_SAMPLES, 50), dtype=np.float32)
        slow[:, :16] = 2.1 + self.rng.normal(0, 0.04, (SLOW_SAMPLES, 16))
        slow[:, 16:30] = 40.0 + self.rng.normal(0, 0.5, (SLOW_SAMPLES, 14))
        slow[:, 30:42] = 1.0 + self.rng.normal(0, 0.03, (SLOW_SAMPLES, 12))
        slow[:, 42:50] = 4.0 + self.rng.normal(0, 0.06, (SLOW_SAMPLES, 8))

        if fault == "overpressure":
            slow[:, 0] = 3.5
        elif fault == "secondary_overpressure":
            slow[:, 15] = 3.5  # last of 16 independently monitored pressure channels
        elif fault == "sensor_dropout":
            slow[:, 0] = np.nan

        di = np.zeros((DIGITAL_SAMPLES, 30), dtype=np.uint8)
        di[:, 1] = ((seq // 2) % 2)  # independent virtual heartbeat input
        if fault == "estop":
            di[:, 0] = 1  # virtual emergency-stop input

        # Independent simulated monitoring; no hardware safety guarantees.
        pressures = slow[:, :16]
        if not self.abort_latched:
            if np.any(di[:, 0]):
                self.abort_latched, self.abort_reason = True, "virtual_estop"
            elif not np.isfinite(pressures).all():
                self.abort_latched, self.abort_reason = True, "invalid_pressure"
            elif np.any(pressures > PRESSURE_LIMIT):
                self.abort_latched, self.abort_reason = True, "overpressure"

        state = self._state(seq)
        cmd = np.zeros(2, dtype=np.float64)
        if state == "START":
            cmd[:] = [2.0, 2.5]
        elif state == "HOLD":
            cmd[:] = [4.0, 4.5]
        # Arbitrary, dimensionless first-order response, not a valve model.
        self.valve_feedback += 0.2 * (cmd / 10.0 - self.valve_feedback)
        ao = np.tile(cmd.astype("<f4"), (DIGITAL_SAMPLES, 1))
        do = np.zeros((DIGITAL_SAMPLES, 30), dtype=np.uint8)
        if state in ("START", "HOLD"):
            do[:, 0] = 1  # virtual run-status line (not an ignition command)
            do[:, 1] = (seq % 2)
        if state == "ABORT":
            ao[:] = 0
            do[:] = 0
            self.valve_feedback[:] = 0  # virtual output-state override

        # Toy flow signals respond to dimensionless virtual actuator feedback.
        # These are not fuel/oxidizer flow models or physical setpoints.
        slow[:, 30] = np.maximum(0, 3 * self.valve_feedback[0] +
                                 self.rng.normal(0, 0.005, SLOW_SAMPLES))
        slow[:, 31] = np.maximum(0, 3 * self.valve_feedback[1] +
                                 self.rng.normal(0, 0.005, SLOW_SAMPLES))

        # This makes FFT verification objective: 1200 Hz is exactly bin 120
        # for 5000 samples taken at 50 kHz (10 Hz resolution).
        ts = t0 + np.arange(FAST_SAMPLES) / FAST_RATE_HZ
        primary = np.sin(2 * np.pi * 1200.0 * ts)
        fast = self.rng.normal(0, 0.02, (FAST_SAMPLES, 25)).astype(np.float32)
        fast[:, 0] += primary.astype(np.float32)
        if fault == "vibration":
            fast[:, 13] += (3.0 * np.sin(2 * np.pi * 1800.0 * ts)).astype(np.float32)

        raw = to_raw_volts(slow)
        arrays = {"slow_raw_v": np.ascontiguousarray(raw, dtype="<f4"),
                  "fast_signal": np.ascontiguousarray(fast, dtype="<f4"),
                  "di": di, "do": do,
                  "ao_v": np.ascontiguousarray(ao, dtype="<f4"),
                  "valve_feedback": np.ascontiguousarray(self.valve_feedback, dtype="<f4")}
        return Frame(sequence=seq, t0_s=t0, state=state, fault=fault,
                     abort_latched=self.abort_latched, abort_reason=self.abort_reason,
                     arrays=arrays)
