# Synthetic DAQ TCP protocol (v1)

**Scope:** Software-only, localhost (`127.0.0.1`). No NI hardware, physical actuator
control, or hardware safety interlock. All states and command values are artificial.

## Backward compatibility

`python daq_sim/tcp_server.py` defaults to `--mode legacy` and preserves the
original 16-byte fixed-width ASCII pressure value at nominally 10 Hz. This mode
requires **exactly 16 bytes per value** in the existing `TCP_Acquisition.vi`.
The TCP protocol is a byte stream; do not assume one read equals one send.

## Full mode wire format

Use `python -m daq_sim.tcp_server --mode full`. Each 100-ms synthetic frame has:

| Offset | Bytes | Encoding | Meaning |
|---|---:|---|---|
| 0 | 4 | `uint32` **big-endian** | Number of bytes *after* these 4 bytes |
| 4 | 4 | `uint32` **big-endian** | UTF-8 JSON header length |
| 8 | variable | UTF-8 JSON | Version, timebase, state, faults, channel catalog, per-array shapes/types, CRC32 |
| following | variable | contiguous binary | Arrays in exact `fields[]` order |

Packet size is bounded at 2,000,000 bytes. Python validates the declared
lengths, shapes, types, and CRC32 of the concatenated array payload. The
arrays are **C-order / time-major**, with channel index in the last dimension.

| Array | Shape per frame | Wire datatype | Meaning |
|---|---|---|---|
| `slow_raw_v` | `(100, 50)` | `<f4` float32 little-endian | 50 calibrated synthetic analog inputs, 1 kHz |
| `fast_signal` | `(5000, 25)` | `<f4` float32 little-endian | 25 synthetic high-frequency signals, 50 kHz |
| `di` | `(10, 30)` | `u1` | Virtual digital inputs, 100 Hz |
| `do` | `(10, 30)` | `u1` | Virtual digital output *states*, 100 Hz |
| `ao_v` | `(10, 2)` | `<f4` float32 little-endian | Virtual analog command *states*, 100 Hz |
| `valve_feedback` | `(2,)` | `<f4` float32 little-endian | Two dimensionless software feedback values |

The 50 slow-channel entries in `slow_catalog` include channel names, declared
synthetic units, `eu_min` and `eu_max`. Convert each raw voltage to engineering
unit with `eu = eu_min + (raw_voltage / 10) * (eu_max - eu_min)`.
Invalid pressure may appear as a float32 NaN in the binary payload.

**Timebase:** `t0_s = sequence * 0.1`, and each sample offset is
`sample_index / channel_rate`. This is index-derived simulation time,
**not** UTC or a synchronized NI sample clock.

**Framing and validation in LabVIEW:** Read exactly 4 bytes for the packet size,
then accumulate exactly that many bytes (loop on partial reads). Take the first
4 bytes of the body as the JSON length. Parse the JSON and split the remaining
array payload using the documented shapes. Decode float32 little-endian values;
reject out-of-range lengths, malformed JSON, unsupported versions, truncated
bodies, invalid CRC, or unknown shapes. A stalled/disconnected connection must
be marked stale and must not present its last sample as live.

The existing `TCP_Acquisition.vi` handles a **different protocol** (legacy
fixed-width pressure). It cannot consume this full mode until its decoder is
extended or a second full-frame receiver is implemented.

## Example

Terminal A:

```bash
python -m daq_sim.tcp_server --mode full --scenario overpressure --fault-frame 8 --frames 12
```

Terminal B:

```bash
python -m daq_sim.tcp_client --frames 12
```

Frame 8 injects synthetic pressure 3.5 sim_bar for one frame; a software-only
3.0 sim_bar threshold latches the simulated ABORT. Later healthy frames remain
in ABORT. Virtual analog and digital outputs are forced to zero. Nothing is
sent to real valves or hardware.

## Throughput budget

`(50 * 1,000) + (25 * 50,000) = 1,300,000` analog samples/s.
Using float32, analog data alone is approximately **5.2 MB/s** (decimal),
or **520,000 bytes per 100-ms frame**. Headers, virtual I/O and capture files
add overhead. This is a **data-model budget**, not a verified OS, TCP, LabVIEW,
or NI-DAQmx throughput guarantee. Recording every frame with `--record-dir`
may add delays on slower hosts.

## LabVIEW parser adversarial checks

- `--scenario secondary_overpressure`: pressure channel 16 trips the simulated Python threshold.
- `--scenario fragmented_frame`: server intentionally sends one complete frame via many small `sendall()` calls. TCP can coalesce these; clients must handle arbitrary `recv()` boundaries regardless.
- `--scenario corrupt_frame`: one payload byte is changed without updating CRC; the Python reference client prints `REJECTED invalid frame: CRC mismatch`. A LabVIEW receiver must also reject it.
- `--scenario disconnect`: the server closes after frame `fault_frame - 1`. The receiver must mark data stale.

The virtual slow flow channels `flow_01` and `flow_02` respond to dimensionless synthetic command feedback. Their quotient may be displayed as a **toy ratio** when the denominator is valid and nonzero, but must not be interpreted as a real propellant mixture ratio.
