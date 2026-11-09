"""GUI components for TCI Audio Interface."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Optional


class TCIAudioGUI:
    """GUI components for the TCI Audio Interface application."""

    def __init__(self, root: tk.Tk, on_start: Callable, on_stop: Callable):
        self.root = root
        self.on_start = on_start
        self.on_stop = on_stop

        # Server configuration variables
        self.server_ip = tk.StringVar(value="192.168.1.200")
        self.server_port = tk.StringVar(value="50001")
        self.monitor_enabled = tk.BooleanVar(value=True)

        # TCI info variables
        self.tci_info = {
            "radio_model": "Unknown",
            "frequency": "0.000 MHz",
            "mode": "USB",
            "power": "0 W",
            "s_meter": "S0"
        }
        self.s_meter_value = 0

        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the user interface."""
        self.root.title("TCI Audio Interface")
        self.root.geometry("640x580")
        self.root.resizable(False, False)

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

        self.start_btn = ttk.Button(btn_frame, text="Start Flux", command=self._on_start_clicked)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))

        self.stop_btn = ttk.Button(btn_frame, text="Stop Flux", command=self._on_stop_clicked, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1)

        # Monitor checkbox
        monitor_frame = ttk.Frame(main_frame)
        monitor_frame.grid(row=4, column=0, sticky=tk.W, pady=(20, 0))
        ttk.Checkbutton(monitor_frame, text="Monitor audio output", variable=self.monitor_enabled).grid(row=0, column=0, sticky=tk.W)

        # TCI Information section
        self.info_frame = ttk.LabelFrame(main_frame, text="TCI Server Information", padding="10")
        self.info_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

        # Radio model
        self.radio_model_label = ttk.Label(self.info_frame, text="Radio: Unknown")
        self.radio_model_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

        # Frequency and mode
        freq_mode_frame = ttk.Frame(self.info_frame)
        freq_mode_frame.grid(row=1, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(freq_mode_frame, text="Frequency:").grid(row=0, column=0, sticky=tk.W)
        self.frequency_label = ttk.Label(freq_mode_frame, text="0.000 MHz")
        self.frequency_label.grid(row=0, column=1, padx=(5, 0))

        ttk.Label(freq_mode_frame, text="Mode:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.mode_label = ttk.Label(freq_mode_frame, text="USB")
        self.mode_label.grid(row=0, column=3, padx=(5, 0))

        # Power and S-meter
        power_s_frame = ttk.Frame(self.info_frame)
        power_s_frame.grid(row=2, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(power_s_frame, text="Power:").grid(row=0, column=0, sticky=tk.W)
        self.power_label = ttk.Label(power_s_frame, text="0 W")
        self.power_label.grid(row=0, column=1, padx=(5, 0))

        ttk.Label(power_s_frame, text="S-Meter:").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        self.s_meter_label = ttk.Label(power_s_frame, text="S0", foreground="blue")
        self.s_meter_label.grid(row=0, column=3, padx=(5, 0))

        # S-meter bar
        s_meter_bar_frame = ttk.Frame(self.info_frame)
        s_meter_bar_frame.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        ttk.Label(s_meter_bar_frame, text="Signal Strength:").grid(row=0, column=0, sticky=tk.W)
        self.s_meter_bar = ttk.Progressbar(s_meter_bar_frame, length=200, maximum=100)
        self.s_meter_bar.grid(row=0, column=1, padx=(5, 0), sticky=tk.W)

        # Info section
        info_frame = ttk.LabelFrame(main_frame, text="Information", padding="10")
        info_frame.grid(row=6, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))

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
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def _on_start_clicked(self) -> None:
        """Handle start button click."""
        if self.on_start:
            self.on_start()

    def _on_stop_clicked(self) -> None:
        """Handle stop button click."""
        if self.on_stop:
            self.on_stop()

    def update_status(self, text: str, color: str = "black") -> None:
        """Update the status label."""
        self.status_label.config(text=f"Status: {text}", foreground=color)
        self.root.update()

    def set_button_states(self, running: bool) -> None:
        """Update button states based on running status."""
        self.start_btn.config(state=tk.DISABLED if running else tk.NORMAL)
        self.stop_btn.config(state=tk.NORMAL if running else tk.DISABLED)

    def update_radio_info(self, radio_model: str) -> None:
        """Update radio model display."""
        self.tci_info["radio_model"] = radio_model
        self.radio_model_label.config(text=f"Radio: {radio_model}")

    def update_frequency(self, frequency_mhz: float) -> None:
        """Update frequency display."""
        self.tci_info["frequency"] = f"{frequency_mhz:.3f} MHz"
        self.frequency_label.config(text=f"{frequency_mhz:.3f} MHz")

    def update_mode(self, mode: str) -> None:
        """Update mode display."""
        self.tci_info["mode"] = mode
        self.mode_label.config(text=mode)

    def update_power(self, power: str) -> None:
        """Update power display."""
        self.tci_info["power"] = power
        self.power_label.config(text=power)

    def update_s_meter(self, s_value: int) -> None:
        """Update S-meter display."""
        from src.tci import TCIParser

        self.s_meter_value = s_value
        s_label = TCIParser.format_s_meter(s_value)
        self.tci_info["s_meter"] = s_label
        self.s_meter_label.config(text=s_label)
        self.s_meter_bar.config(value=s_value)

    def get_server_config(self) -> tuple:
        """Get server IP and port."""
        return self.server_ip.get(), self.server_port.get()

    def is_monitor_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self.monitor_enabled.get()
