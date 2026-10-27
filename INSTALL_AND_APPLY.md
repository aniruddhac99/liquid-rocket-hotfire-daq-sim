# Apply the Python synthesizer extension

From the root of a local checkout of
`aniruddhac99/liquid-rocket-hotfire-daq-sim`:

1. Copy/unzip the contents of this package into the repository root, preserving paths.
2. Confirm `daq_sim/tcp_server.py` has changed (legacy mode is preserved).
3. Install `pip install -r requirements.txt` in a virtual environment.
4. Run `python -m unittest discover -s tests -v`.
5. Run the two-terminal examples in `docs/SIMULATOR_VALIDATION.md`.
6. Commit and push when the results on your Mac are satisfactory.

Suggested Git commands:

```bash
git status
git add daq_sim/ tests/ docs/TCP_PROTOCOL.md docs/SIMULATOR_VALIDATION.md requirements.txt
git commit -m "Extend synthetic DAQ with multichannel TCP and fault tests"
git push origin main
```

**Important:** This package does **not** include or overwrite existing `.vi`
files, `README.md`, or your `.gitignore`. To avoid committing generated data,
add `captures/`, `*.npz`, and `*.npy` to `.gitignore`.

The default server mode has the same 16-byte fixed-width ASCII pressure output
as before; full mode uses a new binary protocol and needs new LabVIEW parsing.
All behavior is virtual and must not be used with actual propulsion hardware.
