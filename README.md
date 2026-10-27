# liquid-rocket-hotfire-daq-sim

**A modular LabVIEW–Python framework for simulated liquid rocket engine ground-test data acquisition, telemetry monitoring, flow-control modeling, and test sequencing.**

## Overview

`liquid-rocket-hotfire-daq-sim` is a software-based engineering framework for designing, simulating, and validating data acquisition (DAQ) and supervisory control workflows associated with liquid rocket engine hot-fire testing.

The framework combines:

- **LabVIEW** for instrumentation interfaces, telemetry visualization, simulated actuator monitoring, and operator controls.
- **Python** for configurable sensor simulation, synthetic telemetry generation, TCP communication, and reproducible fault injection.
- **Modular test components** for pressure monitoring, propellant-flow modeling, data logging, signal analysis, and test sequencing.
- **Scenario-based validation** for nominal operation, sensor faults, telemetry failures, and simulated abort conditions.

The objective is to demonstrate the software architecture and engineering considerations of a ground-test DAQ system without requiring physical propulsion hardware.

The framework is intended to be adaptable to different simulated liquid rocket engine configurations, instrumentation layouts, and test scenarios.

> **Status:** Active development. Initial LabVIEW pressure-monitoring and TCP-acquisition VIs are implemented. Multichannel telemetry, flow simulation, centralized sequencing, and integrated validation are under development.
>
> **Scope:** Software-only simulation. Not qualified for controlling actual propulsion systems or performing hardware safety interlocks.

## 1. System architecture

```text
               LIQUID ROCKET HOT-FIRE DAQ FRAMEWORK
┌─────────────────────────────────────────────────────────┐
│                  TEST CONFIGURATION                     │
│                                                         │
│     Engine Parameters | Sensor Channels | Faults        │
│     Sampling Settings | Test Profiles | Thresholds      │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                  PYTHON SIMULATION LAYER                │
│                                                         │
│   Synthetic Sensors       Test Scenario Generator       │
│   Pressure / Temperature  Nominal / Fault Injection     │
│   Flow / Valve States     Reproducible Test Profiles    │
│                                                         │
│                Telemetry TCP Server                     │
└────────────────────────────┬────────────────────────────┘
                             │
                      TCP Telemetry
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                  LABVIEW ACQUISITION LAYER              │
│                                                         │
│                TCP_Acquisition.vi                       │
│                                                         │
│       Receive | Decode | Validate | Display             │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                MONITORING & ANALYSIS                    │
│                                                         │
│   Simulated_Pressure.vi       Flow_Control.vi            │
│   Pressure Monitoring        Valve / Flow Modeling      │
│                                                         │
│                 Logging_FFT.vi                          │
│             Data Recording / Signal Analysis            │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 TEST SUPERVISION                        │
│                                                         │
│                       Main.vi                           │
│                                                         │
│           PRECHECK → START → HOLD → SHUTDOWN            │
│                         │                               │
│                       ABORT                             │
│                                                         │
│       Operator Dashboard | Status | Alarm Handling      │
└─────────────────────────────────────────────────────────┘
```

*This is the target logical architecture. Individual subsystem interfaces and complete end-to-end integration remain to be implemented.*

## 2. Framework capabilities

### 2.1 Configurable telemetry simulation

Provide simulated instrumentation signals for representative liquid rocket engine subsystems.

Supported or planned signal categories include:

| Category | Example measurements |
|---|---|
| Pressure | Chamber, tank, and feed-line pressure |
| Temperature | Propellant-line and engine temperature |
| Flow | Fuel and oxidizer mass-flow estimates |
| Actuator feedback | Valve position, command state, and feedback |
| Digital telemetry | Interlocks, readiness flags, and fault indicators |
| Test status | Sequence state, elapsed time, and alarm conditions |

The current Python backend generates a single pressure channel near **2.1 bar at approximately 10 Hz**.

Expanded multichannel support is planned.

### 2.2 Telemetry acquisition

`TCP_Acquisition.vi` provides the initial interface between the Python simulator and LabVIEW.

Target capabilities include:

- TCP connection establishment and clean termination.
- Frame decoding and numeric validation.
- Timestamped acquisition.
- Channel-specific measurement handling.
- Timeout and stale-data detection.
- Communication error reporting.

The current implementation receives and displays single-channel pressure telemetry. Robust framing, validation, and recovery tests are pending.

### 2.3 Instrumentation monitoring

`Simulated_Pressure.vi` demonstrates local pressure-signal generation and monitoring.

The framework will support configurable monitoring thresholds, visual status indicators, fault detection, and latched simulated abort states.

The current VI contains a pressure waveform display and an overpressure indication. It is not yet integrated with the TCP acquisition subsystem.

### 2.4 Simulated flow and actuator control

`Flow_Control.vi` will model simplified liquid-propellant feed-system behavior.

Planned capabilities:

- Fuel and oxidizer valve command simulation.
- Simulated valve-position feedback.
- Simplified propellant mass-flow estimation.
- Oxidizer-to-fuel mixture-ratio calculation.
- Command/feedback mismatch detection.
- Simulated safe-state behavior.

This module models actuator and flow response; it does not command physical hardware.

### 2.5 Data logging and signal analysis

`Logging_FFT.vi` will provide:

- Timestamped telemetry recording.
- Channel names and engineering units.
- Time-domain signal visualization.
- FFT-based frequency-domain analysis.
- Synthetic periodic-signal validation.
- Exportable test evidence.

Actual sample timing, effective bandwidth, and frequency resolution will be documented for each simulation mode.

### 2.6 Test sequencing and operator supervision

`Main.vi` will coordinate the subsystem interfaces through a simulated test state machine.

```text
        ┌───────────┐
        │ PRECHECK  │
        └─────┬─────┘
              │
              ▼
        ┌───────────┐
        │   START   │
        └─────┬─────┘
              │
              ▼
        ┌───────────┐
        │   HOLD    │
        └─────┬─────┘
              │
              ▼
        ┌───────────┐
        │ SHUTDOWN  │
        └───────────┘

      FAULT / OPERATOR ABORT
              │
              ▼
        ┌───────────┐
        │   ABORT   │
        │ (Latched) │
        └───────────┘
```

The intended behavior includes explicit state-transition conditions, operator-requested aborts, simulated fault trips, and safe reset requirements.

## 3. Configuration-driven design

A central design objective is to avoid coupling the framework to one predefined engine or sensor layout.

A future test configuration could define:

```yaml
test:
  name: nominal_hotfire_simulation
  duration_s: 60

telemetry:
  host: 127.0.0.1
  port: 5000
  sample_rate_hz: 10

channels:
  - name: feed_pressure
    unit: bar
    nominal: 2.1
    noise_std: 0.05
    trip_high: 3.0

  - name: fuel_flow
    unit: kg/s
    enabled: true

  - name: oxidizer_flow
    unit: kg/s
    enabled: true

faults:
  scenario: nominal
  seed: 42
```

*Illustrative future configuration only. The current server does not parse this YAML schema, and the example threshold is not an engine-qualified operating limit.*

The framework will separate test parameters from simulation code so that different channel sets, signal patterns, and scenarios can reuse the same acquisition and monitoring components.

## 4. Current implementation

| Component | Responsibility | Status |
|---|---|---|
| `daq_sim/tcp_server.py` | Pressure synthesis and TCP streaming | Initial version implemented |
| `Simulated_Pressure.vi` | Waveform visualization and pressure alarm | Initial version implemented |
| `TCP_Acquisition.vi` | TCP telemetry reception and display | Initial version implemented |
| `Flow_Control.vi` | Simulated valves and propellant-flow model | Planned |
| `Logging_FFT.vi` | Timestamped recording and FFT | Planned |
| `Main.vi` | Central orchestration and state machine | Planned |
| Scenario configuration | Reusable test and fault definitions | Planned |
| Automated validation | Repeatable nominal and fault tests | Planned |

The current Python transmitter uses NumPy with random seed `42`, generates nominal pressure samples, and sends fixed-width 16-byte ASCII frames over TCP.

The present protocol has no channel identifiers or timestamps. TCP framing and receiver behavior require additional validation before the communication interface is considered reliable.

## 5. Running the current simulator

### Prerequisites

- Python 3
- NumPy
- NI LabVIEW
- macOS, Windows, or another Python-compatible host for the telemetry generator

The existing LabVIEW VIs were developed using LabVIEW 2026 Community Edition on macOS.

### Start the telemetry server

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install numpy

python daq_sim/tcp_server.py
```

Start `TCP_Acquisition.vi` from LabVIEW and connect to:

```text
Host: 127.0.0.1
Port: 5000
Protocol: TCP
Frame size: 16 bytes
```

The Python server generates pressure readings and transmits them to the connected LabVIEW receiver.

## 6. Verification framework

Validation will cover acquisition, monitoring, communication failures, simulated actuation, and sequencing.

| Test | Scenario | Expected result |
|---|---|---|
| T01 | Nominal pressure | Continuous display without alarm |
| T02 | Overpressure injection | Alarm and latched abort |
| T03 | Pressure recovery | Abort persists until valid reset |
| T04 | Nominal TCP streaming | Complete frames decoded correctly |
| T05 | TCP interruption | Disconnect and stale-data indication |
| T06 | Invalid telemetry | Invalid sample rejected |
| T07 | Valve-state changes | Consistent simulated flow response |
| T08 | Data recording | Timestamped measurements available |
| T09 | Periodic signal injection | Expected FFT frequency peak |
| T10 | Sequence fault | Transition to simulated ABORT |

These are planned test cases, not completed acceptance-test results.

## 7. DAQ scalability and engineering considerations

The broader design exercise considers the following instrumentation requirements:

| I/O category | Design target |
|---|---:|
| Slow analog inputs | 50 channels at 1 kHz |
| Fast analog inputs | 25 channels at 50 kHz |
| Digital inputs | 30 |
| Digital outputs | 30 |
| Analog outputs | 2 |

These targets inform the architecture, bandwidth calculations, buffer design, channel grouping, and proposed hardware selection.

They are **not implemented hardware capabilities** of the current simulator.

The framework currently operates as a single-channel, approximately 10 Hz software demonstration.

Future extensions may separate low-rate supervisory telemetry from high-rate waveform acquisition, buffering, and offline analysis.

## 8. Repository structure

```text
liquid-rocket-hotfire-daq-sim/
│
├── README.md
├── .gitignore
│
├── Simulated_Pressure.vi
├── TCP_Acquisition.vi
│
├── daq_sim/
│   └── tcp_server.py
│
└── docs/
    ├── ARCHITECTURE.md
    └── REQUIREMENTS.md
```

Proposed future structure:

```text
liquid-rocket-hotfire-daq-sim/
│
├── labview/
│   ├── Main.vi
│   ├── TCP_Acquisition.vi
│   ├── Simulated_Pressure.vi
│   ├── Flow_Control.vi
│   └── Logging_FFT.vi
│
├── daq_sim/
│   ├── tcp_server.py
│   ├── telemetry.py
│   ├── scenarios.py
│   └── faults.py
│
├── config/
│   ├── nominal.yaml
│   └── fault_scenarios.yaml
│
├── tests/
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── REQUIREMENTS.md
│   ├── PROTOCOL.md
│   └── VALIDATION.md
│
└── README.md
```

The proposed structure separates the simulator, LabVIEW interfaces, test configurations, and validation artifacts.

## 9. Development roadmap

**Phase 1 — Basic telemetry acquisition**

- Establish Python-to-LabVIEW TCP communication.
- Visualize nominal pressure telemetry.
- Validate message framing and basic error handling.

**Phase 2 — Reproducible simulation**

- Add multiple sensor channels.
- Introduce named operating scenarios.
- Add reproducible overpressure and communication faults.
- Define a versioned, structured telemetry protocol.

**Phase 3 — Test subsystem modeling**

- Implement simulated valve and flow behavior.
- Add timestamped telemetry logging.
- Demonstrate signal analysis with FFT.

**Phase 4 — System integration**

- Build the main supervisory VI.
- Integrate monitoring, acquisition, logging, and simulated flow control.
- Implement test sequencing and latched abort behavior.

**Phase 5 — Verification and documentation**

- Execute nominal and fault-injection test cases.
- Record results and known limitations.
- Document sampling, throughput, buffer sizing, and architecture tradeoffs.
- Compare the simulated implementation against the wider DAQ requirements.

## 10. Scope and safety

This framework supports the study of software architecture for ground-test instrumentation, telemetry processing, simulated process control, and fault-handling workflows.

It does not provide deterministic real-time acquisition, validated NI-DAQmx hardware integration, hardware-qualified interlocks, or actual propulsion-system control.

All valve commands, flow responses, shutdown states, and abort actions are simulated.

**The framework must not be connected to or relied upon to control a real rocket engine or other hazardous industrial equipment without a separately engineered and independently validated hardware safety system.**

---

**Project:** `liquid-rocket-hotfire-daq-sim`  
**Domain:** Liquid Rocket Propulsion | Ground-Test Instrumentation | DAQ Simulation  
**Technologies:** LabVIEW, Python, NumPy, TCP/IP  
**Focus:** Modular Acquisition, Telemetry, Simulation, Monitoring, and Verification
