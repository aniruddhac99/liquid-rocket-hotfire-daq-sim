# liquid-rocket-hotfire-daq-sim

**LabVIEW-based data acquisition, monitoring, and simulated flow-control system for a liquid rocket engine hot-fire test.**

This project explores the design of a ground-test data acquisition (DAQ) system using **LabVIEW** for operator-facing monitoring and control and **Python** for reproducible synthetic telemetry. The goal is to demonstrate acquisition, signal visualization, safety monitoring, data logging, and a simple test sequence without requiring physical rocket-engine hardware.

> **Project status:** Work in progress. Two LabVIEW VIs exist (`Simulated_Pressure.vi` and `TCP_Acquisition.vi`), with validation and fault-handling improvements pending. Three additional VIs are planned. This is a software-only engineering demonstrator, **not** a flight-ready or hardware-qualified safety/control system.

## System overview

```text
               Python telemetry synthesizer
                  daq_sim/tcp_server.py
                             |
                 TCP 127.0.0.1:5000
                             |
                    TCP_Acquisition.vi
                             |
                   Parsed pressure data
                             |
       +---------------------+---------------------+
       |                     |                     |
Simulated_Pressure.vi   Flow_Control.vi       Logging_FFT.vi
pressure/alarm demo     valve/flow model      logs + analysis
       |                     |                     |
       +---------------------+---------------------+
                             |
                          Main.vi
                sequencing + operator view
                        (planned)
```

This diagram represents the **target architecture**, not an already wired or integrated system. In the current implementation, the pressure simulation VI also has an independent LabVIEW-generated signal; it is not yet verified as a consumer of the TCP VI's output.

## Implementation status

| Component | Purpose | Status |
|---|---|---|
| `daq_sim/tcp_server.py` | Generate single-channel simulated pressure and stream over TCP | **Implemented**; basic transmission observed |
| `Simulated_Pressure.vi` | Display simulated pressure and threshold indication | **Initial version built**; fault injection, latched abort, and formal tests pending |
| `TCP_Acquisition.vi` | Receive and display incoming pressure telemetry | **Initial version built**; framing, parsing, disconnect behavior, and repeatable validation pending |
| `Flow_Control.vi` | Simulate valve commands, valve feedback, flow, and mixture ratio | **Planned** |
| `Logging_FFT.vi` | Timestamped logging, waveform inspection, and FFT analysis | **Planned** |
| `Main.vi` | Integrate subsystems and implement precheck/start/hold/shutdown sequencing | **Planned** |

## Current Python telemetry synthesizer

The existing `daq_sim/tcp_server.py`:

- Uses NumPy's reproducible random generator (seed `42`).
- Simulates pressure near **2.1 bar** with Gaussian noise (standard deviation **0.05 bar**).
- Listens on **127.0.0.1:5000** and accepts a single client at a time.
- Sends a **16-character, fixed-width ASCII numeric pressure value** using `f"{pressure:016.6f}"`.
- Targets one new reading every **0.1 seconds** (nominally **10 Hz**).
- Handles common client disconnect exceptions and waits for another connection.

**Protocol note:** The server sends a continuous TCP byte stream, without newline delimiters, timestamps, units, or channel identifiers. Each numeric frame is 16 bytes, so the LabVIEW receiver must buffer and process complete 16-byte frames; a single TCP read is not guaranteed to correspond to one send. A nominal 10 Hz loop is **not** a guaranteed hardware sample rate.

### Requirements

- Python 3 with NumPy
- NI LabVIEW (VIs created using LabVIEW 2026 Community Edition on macOS)
- Both applications on the same machine for the current localhost configuration

### Run the synthesizer

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy
python daq_sim/tcp_server.py
```

Expected initial output:

```text
DAQ Simulator listening on 127.0.0.1:5000
```

Next, open `TCP_Acquisition.vi` in LabVIEW, configure the host as `127.0.0.1` and port as `5000`, and run the VI. When connected, the Python console should show successive values resembling:

```text
LabVIEW connected: (...)
Pressure: 2.186 bar
Pressure: 2.051 bar
Pressure: 2.088 bar
```

These are illustrative readings, not acceptance-test results. Stop the server with **Ctrl+C**.

## Five-VI design

### 1. `Simulated_Pressure.vi` — pressure monitoring

A local LabVIEW pressure-signal demonstrator with waveform display and an overpressure indicator.

**Next steps:** establish a documented trip threshold, provide manual fault injection, latch an ABORT state after a trip, and require explicit reset under safe conditions. Test nominal, trip, and reset behavior.

### 2. `TCP_Acquisition.vi` — network acquisition

Receives pressure telemetry from the Python TCP server and displays incoming values.

**Next steps:** confirm fixed-width parsing across partial/coalesced reads, implement timeouts and clean disconnection, reject invalid values, and surface stale-data conditions to the operator.

### 3. `Flow_Control.vi` — simulated actuators (planned)

Represent valve open/close commands, feedback states, and simplified fuel/oxidizer flow estimates. Calculate mixture ratio only when both modeled flows are valid and the denominator is nonzero. No physical valves are controlled.

### 4. `Logging_FFT.vi` — recording and signal analysis (planned)

Record samples with timestamps and channel identifiers, plot time-domain data, and analyze an injected periodic test signal using an FFT. Document the sample rate and FFT frequency resolution; do not infer high-rate DAQ performance from the current 10 Hz TCP feed.

### 5. `Main.vi` — coordination and sequence control (planned)

Provide a top-level operator view and a simple state machine:

```text
PRECHECK --> START --> HOLD --> SHUTDOWN
    |         |        |
    +---------+--------+--> ABORT (latched)
```

Model safe shutdown/abort transitions and surface telemetry and simulated actuator states. Integration and end-to-end behavior are not yet verified.

## Verification plan

The following are **planned acceptance checks**, not claims of passing tests:

| ID | Scenario | Expected behavior |
|---|---|---|
| T01 | Normal pressure | Plot and numeric display update without alarm |
| T02 | High-pressure injection | Trip threshold and latch abort |
| T03 | Pressure returns to normal after trip | Abort remains latched until authorized reset |
| T04 | Python server running | LabVIEW connects and decodes repeated frames correctly |
| T05 | Python server stopped or disconnected | Timeout/disconnect surfaced; no stale pressure presented as live |
| T06 | Partial or invalid TCP frame | Frame buffered/rejected without silently producing a valid reading |
| T07 | Simulated valve commands | Valve feedback and modeled flows update consistently |
| T08 | Logging enabled | Records contain usable timestamps, units, and sample values |
| T09 | Injected periodic waveform | FFT peak appears near the known injection frequency |
| T10 | Sequence or safety fault | Main state machine transitions to latched ABORT |

Validation evidence should include screenshots of front panels and block diagrams, selected terminal logs, a concise test-results table, and any known failures or limitations.

## Engineering scope and limitations

The wider DAQ design exercise considers **50 slow analog channels at 1 kHz, 25 fast analog channels at 50 kHz, 30 digital inputs, 30 digital outputs, and 2 analog outputs**. These are **design targets**, not capabilities currently delivered by this repository.

The present backend sends **one simulated pressure channel at approximately 10 Hz**. It does not implement multichannel, deterministic acquisition, synchronized timestamps, physical NI-DAQmx acquisition, real actuator I/O, or validated high-throughput disk logging. The NI Measurement & Automation Explorer (NI MAX) hardware simulation workflow is also not demonstrated in the current macOS setup.

A future expanded synthesizer may add timestamped multichannel data, reproducible fault scenarios, simulated digital I/O and actuator feedback, and periodic signals for FFT tests. That extension should retain a compatibility mode for the current fixed-width pressure TCP receiver.

**Safety:** This repository is intended solely for offline simulation and software prototyping. It must not be used to operate real propulsion hardware or serve as an independent hardware safety interlock.

## Repository layout

```text
.
├── README.md
├── .gitignore
├── Simulated_Pressure.vi
├── TCP_Acquisition.vi
├── daq_sim/
│   └── tcp_server.py
└── docs/
    ├── ARCHITECTURE.md
    └── REQUIREMENTS.md

# Planned additions:
# Flow_Control.vi
# Logging_FFT.vi
# Main.vi
```

## Development roadmap

1. Validate pressure monitoring and TCP acquisition VIs with recorded results.
2. Extend the synthesizer to support fault injection and structured test signals while preserving the basic protocol.
3. Build and test `Flow_Control.vi`.
4. Build and test `Logging_FFT.vi`.
5. Integrate the five VIs using `Main.vi`; run nominal and fault scenarios.
6. Document architectural assumptions, test evidence, resource estimates, and unmet hardware requirements.

