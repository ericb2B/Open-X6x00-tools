import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import subprocess
import threading
import os
import asyncio
import numpy as np
import sounddevice as sd
import websockets
from concurrent.futures import ThreadPoolExecutor

class TCIAudioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TCI Audio Interface")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        # Variables
        self.server_ip = tk.StringVar(value="192.168.1.200")
        self.server_port = tk.StringVar(value="50001")
        self.is_running = False
        self.stream_thread = None
        self.executor = ThreadPoolExecutor(max_workers=1)

        # Directory setup
        self.dir_path = os.path.expanduser("~/tci-audio")
        self.python_path = os.path.join(self.dir_path, "venv/bin/python")

        self.setup_ui()

    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Server address section
        ttk.Label(main_frame, text="Server Address:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, pady=(0, 10)
        )

        ip_frame = ttk.Frame(main_frame)
        ip_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 15))

        ttk.Label(ip_frame, text="IP:").grid(row=0, column=0, sticky=tk.W)
        self.ip_entry = ttk.Entry(ip_frame, textvariable=self.server_ip, width=15)
        self.ip_entry.grid(row=0, column=1, padx=(5, 10))

        ttk.Label(ip_frame, text="Port:").grid(row=0, column=2, sticky=tk.W)
        self.port_entry = ttk.Entry(ip_frame, textvariable=self.server_port, width=8)
        self.port_entry.grid(row=0, column=3, padx=(5, 0))

        # Status label
        self.status_label = ttk.Label(main_frame, text="Status: Stopped", foreground="red")
        self.status_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 15))

        # Button frame
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        self.start_btn = ttk.Button(btn_frame, text="Start Flux", command=self.start_flux)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))

        self.stop_btn = ttk.Button(btn_frame, text="Stop Flux", command=self.stop_flux, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1)

        # Info section
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        ttk.Label(info_frame, text="• Creates virtual audio devices (tci_rx sink and tci_micro source)").grid(
            row=0, column=0, sticky=tk.W, pady=(0, 5)
        )
        ttk.Label(info_frame, text="• Connects to X6100 radio via WebSocket").grid(
            row=1, column=0, sticky=tk.W, pady=(0, 5)
        )
        ttk.Label(info_frame, text="• Routes audio from radio to virtual microphone").grid(
            row=2, column=0, sticky=tk.W
        )

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)

    def start_flux(self):
        if self.is_running:
            return

        # Validate server address
        try:
            ip = self.server_ip.get()
            port = int(self.server_port.get())
            if not (1 <= len(ip.split(".")) == 4 and all(0 <= int(x) <= 255 for x in ip.split("."))):
                raise ValueError("Invalid IP address")
            if not (1 <= port <= 65535):
                raise ValueError("Invalid port number")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid server address: {e}")
            return

        self.is_running = True
        self.update_status("Starting...", "orange")

        # Start the flux in a separate thread
        self.stream_thread = threading.Thread(target=self.run_flux, daemon=True)
        self.stream_thread.start()

        # Update button states
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

    def stop_flux(self):
        if not self.is_running:
            return

        self.is_running = False
        self.update_status("Stopping...", "orange")

        # Give it time to stop gracefully
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=3)

        self.update_status("Stopped", "red")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

    def update_status(self, text, color):
        self.status_label.config(text=f"Status: {text}", foreground=color)
        self.root.update()

    def run_flux(self):
        try:
            # Check if Python venv exists
            if not os.path.exists(self.python_path):
                raise RuntimeError(f"Python venv not found at {self.python_path}")

            # Check required modules
            check_modules_cmd = [
                self.python_path, "-c",
                "import numpy, sounddevice, websockets"
            ]
            result = subprocess.run(check_modules_cmd, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError("Missing Python modules in venv (numpy, sounddevice, websockets)")

            # Create virtual audio devices
            self.create_virtual_devices()

            # Start audio streaming
            asyncio.run(self.start_audio_stream())

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.is_running = False
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.update_status("Error", "red"))

    def create_virtual_devices(self):
        try:
            # Create null sink for RX
            subprocess.run([
                "pactl", "load-module", "module-null-sink",
                f"sink_name=tci_rx",
                "rate=48000",
                "channels=2",
                "sink_properties=device.description=TCI_RX"
            ], check=True, capture_output=True)

            # Create remap source for microphone
            subprocess.run([
                "pactl", "load-module", "module-remap-source",
                "master=tci_rx.monitor",
                "source_name=tci_micro",
                "source_properties=device.description=TCI_Microphone"
            ], check=True, capture_output=True)

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create virtual audio devices: {e.stderr.decode()}")

    async def start_audio_stream(self):
        uri = f"ws://{self.server_ip.get()}:{self.server_port.get()}"

        # Find the tci_rx device
        devices = sd.query_devices()
        device = next(
            (i for i, d in enumerate(devices)
             if d["name"] == "tci_rx" and d["max_output_channels"] >= 2),
            None
        )

        if device is None:
            raise RuntimeError("Virtual audio output tci_rx not found")

        print(f"Using audio device: {device} - {devices[device]['name']}")

        async with websockets.connect(uri, max_size=None, ping_interval=20) as ws:
            await ws.send("audio_start:0;")
            print("TCI connected and receiving audio")

            with sd.OutputStream(
                device=device,
                samplerate=48000,
                channels=2,
                dtype="float32",
                blocksize=0
            ) as output:
                while self.is_running:
                    try:
                        data = await asyncio.wait_for(ws.recv(), timeout=1.0)

                        if not isinstance(data, bytes):
                            continue

                        if len(data) != 16448:
                            continue

                        audio = np.frombuffer(data[64:], dtype="<f4")

                        if audio.size != 4096:
                            continue

                        audio = audio.reshape(-1, 2)
                        output.write(audio)

                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        if self.is_running:
                            raise RuntimeError(f"Streaming error: {e}")

        # Cleanup on exit
        self.cleanup_devices()

    def cleanup_devices(self):
        try:
            # Unload modules
            subprocess.run(["pactl", "unload-module", "module-remap-source"],
                          capture_output=True)
            subprocess.run(["pactl", "unload-module", "module-null-sink"],
                          capture_output=True)
        except Exception:
            pass


def main():
    root = tk.Tk()
    app = TCIAudioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
