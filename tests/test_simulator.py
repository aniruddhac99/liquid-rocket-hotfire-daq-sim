"""Synthetic DAQ reproducibility, fault, packet and FFT acceptance tests."""
import socket
import struct
import threading
import unittest
import numpy as np

from daq_sim.core import Simulator, channel_catalog, to_raw_volts, from_raw_volts, FAST_RATE_HZ
from daq_sim.protocol import encode_frame, decode_frame, FrameDecoder, ProtocolError, recv_frame


class SimulatorTests(unittest.TestCase):
    def test_inventory_and_shapes(self):
        a = Simulator().next_frame()
        self.assertEqual(len(channel_catalog()), 50)
        self.assertEqual({k: v.shape for k, v in a.arrays.items()}, {
            "slow_raw_v": (100, 50), "fast_signal": (5000, 25),
            "di": (10, 30), "do": (10, 30), "ao_v": (10, 2),
            "valve_feedback": (2,)})

    def test_scale_roundtrip(self):
        source = from_raw_volts(Simulator().next_frame().arrays["slow_raw_v"])
        np.testing.assert_allclose(from_raw_volts(to_raw_volts(source)), source, atol=1e-5)

    def test_seed_reproducibility(self):
        a = Simulator(seed=42).next_frame()
        b = Simulator(seed=42).next_frame()
        for key in a.arrays:
            np.testing.assert_array_equal(a.arrays[key], b.arrays[key])

    def test_normal_state_path(self):
        sim = Simulator()
        frames = [sim.next_frame() for _ in range(22)]
        self.assertEqual([f.state for f in (frames[0], frames[2], frames[7], frames[18])],
                         ["PRECHECK", "START", "HOLD", "SHUTDOWN"])
        self.assertFalse(any(f.abort_latched for f in frames))

    def test_overpressure_latches_after_transient(self):
        sim = Simulator(scenario="overpressure", fault_frame=8)
        frames = [sim.next_frame() for _ in range(11)]
        self.assertFalse(frames[7].abort_latched)
        self.assertEqual(frames[8].abort_reason, "overpressure")
        self.assertEqual(frames[10].state, "ABORT")
        self.assertEqual(frames[10].fault, "none")
        self.assertTrue(np.all(frames[10].arrays["ao_v"] == 0))
        self.assertTrue(np.all(frames[10].arrays["do"] == 0))

    def test_secondary_pressure_channel_trips(self):
        sim = Simulator(scenario="secondary_overpressure", fault_frame=3)
        for _ in range(4):
            f = sim.next_frame()
        self.assertEqual(f.abort_reason, "overpressure")
        self.assertGreater(float(from_raw_volts(f.arrays["slow_raw_v"])[0, 15]), 3.0)

    def test_flow_feedback_tracks_virtual_commands(self):
        sim = Simulator()
        precheck = sim.next_frame()
        sim.next_frame()
        active = sim.next_frame()
        x = from_raw_volts(precheck.arrays["slow_raw_v"])
        y = from_raw_volts(active.arrays["slow_raw_v"])
        self.assertGreater(float(np.mean(y[:, 30])), float(np.mean(x[:, 30])) + 0.05)
        self.assertGreater(float(np.mean(y[:, 31])), float(np.mean(x[:, 31])) + 0.05)

    def test_sensor_dropout_aborts(self):
        sim = Simulator(scenario="sensor_dropout", fault_frame=3)
        for _ in range(4):
            f = sim.next_frame()
        self.assertEqual(f.abort_reason, "invalid_pressure")
        self.assertTrue(np.isnan(f.arrays["slow_raw_v"][:, 0]).all())

    def test_virtual_estop_aborts(self):
        sim = Simulator(scenario="estop", fault_frame=3)
        for _ in range(4):
            f = sim.next_frame()
        self.assertEqual(f.abort_reason, "virtual_estop")
        self.assertTrue(np.all(f.arrays["ao_v"] == 0))
        self.assertTrue(np.all(f.arrays["do"] == 0))

    def test_valve_feedback_changes_with_commands(self):
        sim = Simulator()
        sim.next_frame()
        sim.next_frame()
        f = sim.next_frame()
        self.assertGreater(float(f.arrays["valve_feedback"][0]), 0)
        self.assertGreater(float(f.arrays["ao_v"][0, 0]), 0)

    def test_fft_peak(self):
        x = Simulator().next_frame().arrays["fast_signal"][:, 0]
        f = np.fft.rfftfreq(len(x), 1 / FAST_RATE_HZ)
        power = np.abs(np.fft.rfft(x))
        self.assertAlmostEqual(float(f[np.argmax(power[1:]) + 1]), 1200, delta=10)

    def test_injected_vibration_has_stronger_1800_hz_bin(self):
        sim = Simulator(scenario="vibration", fault_frame=1)
        before = sim.next_frame().arrays["fast_signal"][:, 13]
        after = sim.next_frame().arrays["fast_signal"][:, 13]
        self.assertGreater(np.abs(np.fft.rfft(after))[180], np.abs(np.fft.rfft(before))[180] * 10)
        self.assertFalse(sim.abort_latched)


class ProtocolTests(unittest.TestCase):
    def test_full_roundtrip(self):
        frame = Simulator().next_frame()
        packet = encode_frame(frame)
        meta, arrays = decode_frame(packet)
        self.assertEqual(meta["sequence"], 0)
        self.assertEqual(meta["rates_hz"]["fast_signal"], 50_000)
        for key in frame.arrays:
            np.testing.assert_array_equal(arrays[key], frame.arrays[key])

    def test_tcp_arbitrary_chunks(self):
        packet = encode_frame(Simulator().next_frame())
        stream = packet + packet
        decoder = FrameDecoder()
        frames = []
        for i in range(0, len(stream), 327):
            frames.extend(decoder.feed(stream[i:i + 327]))
        self.assertEqual([f[0]["sequence"] for f in frames], [0, 0])
        self.assertEqual(len(decoder.buffer), 0)

    def test_crc_failure(self):
        packet = bytearray(encode_frame(Simulator().next_frame()))
        packet[-1] ^= 1
        with self.assertRaisesRegex(ProtocolError, "CRC"):
            decode_frame(bytes(packet))

    def test_length_validation(self):
        decoder = FrameDecoder()
        with self.assertRaisesRegex(ProtocolError, "Out-of-range"):
            decoder.feed(struct.pack(">I", 9_999_999))

    def test_socketpair_fullframe(self):
        a, b = socket.socketpair()
        try:
            packet = encode_frame(Simulator().next_frame())
            sender = threading.Thread(target=a.sendall, args=(packet,))
            sender.start()
            meta, arrays = recv_frame(b)
            sender.join(timeout=2)
            self.assertFalse(sender.is_alive())
            self.assertEqual(meta["sequence"], 0)
            self.assertEqual(arrays["slow_raw_v"].shape, (100, 50))
        finally:
            a.close()
            b.close()

    def test_disconnect_during_frame(self):
        a, b = socket.socketpair()
        try:
            packet = encode_frame(Simulator().next_frame())
            a.sendall(packet[:500])
            a.close()
            with self.assertRaises(EOFError):
                recv_frame(b)
        finally:
            b.close()


if __name__ == "__main__":
    unittest.main()
