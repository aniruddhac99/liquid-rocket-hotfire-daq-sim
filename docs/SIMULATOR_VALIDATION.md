# Synthetic Python DAQ validation

All tests below are software-only. The reference Python frame generator has
no connection to physical hardware or real propulsion controls.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

The initial extension was checked locally using Python, NumPy and 18
`unittest` cases. On the target MacBook, rerun these tests and record
actual results rather than copying the reference results as evidence.

## Mode A: legacy VI compatibility

Terminal A:

```bash
python daq_sim/tcp_server.py
```

Run the existing `TCP_Acquisition.vi` on port 5000. Its TCP read logic should
accumulate **exactly 16 bytes** before converting the ASCII numeric value.
Observe pressure near 2.1 bar. Disconnect/restart the VI and verify recovery.
This mode does not carry pressure faults or multi-channel data.

## Mode B: full synthetic multi-rate stream

Terminal A:

```bash
python -m daq_sim.tcp_server --mode full --scenario nominal --frames 24
```

Terminal B:

```bash
python -m daq_sim.tcp_client --frames 24
```

Expect `PRECHECK → START → HOLD → SHUTDOWN`, 50 slow channels, 25 fast
channels, 30 DI, 30 DO, and 2 AO. The client confirms first-channel pressure,
state, ABORT and 1,200 Hz FFT peak. This tests Python TCP parsing, not LabVIEW.

## Repeatable fault scenarios

Run the server in terminal A, then run the client in terminal B. Change the
scenario each time. Stop the server between scenarios; default port is 5000.

| Scenario | Server argument | Expected Python behavior |
|---|---|---|
| Normal | `--scenario nominal --frames 24` | No abort, complete states |
| Overpressure | `--scenario overpressure --fault-frame 8 --frames 12` | One frame at 3.5 sim_bar; latches ABORT and zero outputs |
| Other pressure input | `--scenario secondary_overpressure --fault-frame 8 --frames 12` | Pressure channel 16 exceeds threshold and triggers ABORT |
| Sensor failure | `--scenario sensor_dropout --fault-frame 8 --frames 12` | NaN synthetic pressure; latches invalid-pressure ABORT |
| E-stop | `--scenario estop --fault-frame 8 --frames 12` | `DI_01=1` for one frame; latches virtual E-stop ABORT |
| Vibration | `--scenario vibration --fault-frame 8 --frames 12` | Adds 1,800 Hz test tone to vibration channel 01; no automatic abort |
| Disconnect | `--scenario disconnect --fault-frame 8 --frames 12` | Connection deliberately closes before frame 8; consumer detects EOF |
| Corrupted TCP frame | `--scenario corrupt_frame --fault-frame 8 --frames 12` | CRC mismatch must be rejected, not treated as a valid pressure value |
| Split TCP send | `--scenario fragmented_frame --fault-frame 8 --frames 12` | The receiver reconstructs the full frame from chunks |

Example with recording:

```bash
python -m daq_sim.tcp_server --mode full --scenario overpressure \
  --fault-frame 8 --frames 12 --record-dir captures/overpressure
```

The optional per-frame `.npz` files are local **Python reference captures**, not
LabVIEW TDMS logging and not guaranteed full-rate disk acquisition. Do not
commit large generated captures to the source repository.

## Requirements not yet proven by this Python test

- `TCP_Acquisition.vi` full-frame byte parsing, data scaling and stale-data handling
- independent LabVIEW abort logic and virtual control-output arbitration
- LabVIEW state integration and live command-feedback loops
- native LabVIEW TDMS logging/readback, FFT display and timestamp integrity
- stable end-to-end 1.3-million-samples/s processing on the target host
- NI-DAQmx/NI MAX simulated hardware, actual sensors, or hardware safety

Update the status table and collect screenshots/terminal outputs when these
steps have been validated in LabVIEW.
