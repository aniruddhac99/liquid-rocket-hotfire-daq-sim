
import socket
import time
import numpy as np

HOST = "127.0.0.1"
PORT = 5000

rng = np.random.default_rng(42)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)

    print(f"DAQ Simulator listening on {HOST}:{PORT}", flush=True)

    while True:
        conn, addr = server.accept()
        print(f"LabVIEW connected: {addr}", flush=True)

        try:
            with conn:
                while True:
                    pressure = 2.1 + rng.normal(0, 0.05)
                    message = f"{pressure:016.6f}".encode("ascii")
                    conn.sendall(message)

                    print(f"Pressure: {pressure:.3f} bar", flush=True)
                    time.sleep(0.1)

        except (BrokenPipeError, ConnectionResetError):
            print("LabVIEW disconnected", flush=True)

