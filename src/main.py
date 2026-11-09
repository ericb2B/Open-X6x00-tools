"""Main entry point for TCI Audio Interface."""

import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import os
import asyncio
import time

# Import modules with proper path handling
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))

try:
    from config import (
        DEFAULT_SERVER_IP, DEFAULT_SERVER_PORT, PYTHON_PATH,
        WINDOW_TITLE, WINDOW_SIZE, WINDOW_RESIZABLE
    )
    from audio_devices import AudioDeviceManager
    from audio import AudioMonitor, AudioStreamer
    from tci import TCIWebSocketClient, TCIParser
    from gui import TCIAudioGUI
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback for direct execution
    DEFAULT_SERVER_IP = "192.168.1.200"
    DEFAULT_SERVER_PORT = "50001"
    PYTHON_PATH = os.path.expanduser("~/tci-audio/venv/bin/python")
    WINDOW_TITLE = "TCI Audio Interface"
    WINDOW_SIZE = "640x580"
    WINDOW_RESIZABLE = False
    from src.config import *
    from src.audio_devices import *
    from src.audio import *
    from src.tci import *
    from src.gui import *


class TCIAudioApp:
    """Main application class for TCI Audio Interface."""

    def __init__(self, root: tk.Tk):
        self.root = root

        # State variables
        self.is_running = False
        self.stream_thread = None
        self.tci_client = None
        
        # Audio components
        self.audio_device_manager = AudioDeviceManager()
        self.audio_monitor = AudioMonitor()
        self.audio_streamer = AudioStreamer(self.audio_monitor, self._on_s_meter_update)

        # Setup GUI
        self.gui = TCIAudioGUI(
            root,
            on_start=self.start_flux,
            on_stop=self.stop_flux
        )

        # Override window properties
        self.root.title(WINDOW_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)
        
        # Set initial monitor state from GUI
        self.audio_monitor.enabled = self.gui.is_monitor_enabled()
    
    def _on_s_meter_update(self, s_value: int) -> None:
        """Handle S-meter update from audio streamer."""
        self.gui.update_s_meter(s_value)

    def start_flux(self) -> None:
        """Start the audio streaming process."""
        if self.is_running:
            return

        # Validate server address
        try:
            ip, port = self.gui.get_server_config()
            if not self._validate_server_address(ip, int(port)):
                return
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid server address: {e}")
            return

        self.is_running = True
        self.gui.update_status("Starting...", "orange")
        self.gui.set_button_states(True)

        # Start streaming in a separate thread
        self.stream_thread = threading.Thread(target=self._run_flux, daemon=True)
        self.stream_thread.start()

    def _validate_server_address(self, ip: str, port: int) -> bool:
        """Validate server IP address and port."""
        parts = ip.split(".")
        if len(parts) != 4 or not all(0 <= int(x) <= 255 for x in parts):
            messagebox.showerror("Error", "Invalid IP address")
            return False
        if not 1 <= port <= 65535:
            messagebox.showerror("Error", "Invalid port number")
            return False
        return True

    def stop_flux(self) -> None:
        """Stop the audio streaming process."""
        if not self.is_running:
            return

        self.is_running = False
        self.gui.update_status("Stopping...", "orange")

        # Stop audio streamer
        self.audio_streamer.stop()

        # Stop monitoring
        self.audio_monitor.stop_monitoring()
        
        # Give it time to stop gracefully
        if self.stream_thread and self.stream_thread.is_alive():
            self.stream_thread.join(timeout=3)

        # Cleanup devices
        try:
            self.audio_device_manager.cleanup_devices()
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        self.gui.update_status("Stopped", "red")
        self.gui.set_button_states(False)

    def _run_flux(self) -> None:
        """Run the audio streaming process in a thread."""
        try:
            # Check if Python venv exists
            if not os.path.exists(PYTHON_PATH):
                raise RuntimeError(f"Python venv not found at {PYTHON_PATH}")

            # Check required modules
            check_modules_cmd = [
                PYTHON_PATH, "-c",
                "import numpy, sounddevice, websockets"
            ]
            result = subprocess.run(check_modules_cmd, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError("Missing Python modules in venv (numpy, sounddevice, websockets)")

            # Create virtual audio devices
            self.audio_device_manager.create_virtual_devices()

            # Check what modules are loaded
            self.audio_device_manager.check_pulseaudio_modules()
            
            # Check sinks and sources directly via pactl
            print("=== PULSEAUDIO SINKS ===")
            sinks = self.audio_device_manager.check_sinks()
            for sink_id, sink_name in sinks:
                print(f"  Sink {sink_id}: {sink_name}")
            
            print("=== PULSEAUDIO SOURCES ===")
            sources = self.audio_device_manager.check_sources()
            for source_id, source_name in sources:
                print(f"  Source {source_id}: {source_name}")
            print("==========================")
            
            # List all devices to see what's available
            print("=== ALL AUDIO DEVICES ===")
            self.audio_device_manager.list_audio_devices()
            print("==========================")
            
            # Verify devices were created
            time.sleep(2)  # Give time for devices to be registered
            
            # Get server config
            ip, port = self.gui.get_server_config()

            # Create TCI client
            self.tci_client = TCIWebSocketClient(ip, port)
            
            # Find audio device - try multiple approaches
            device_index = None
            
            # First approach: direct search
            device_index = self.audio_streamer.find_tci_device()
            
            if device_index is None:
                # Second approach: check all devices manually
                import sounddevice as sd
                devices = sd.query_devices()
                print("Manual device check:")
                for i, device in enumerate(devices):
                    print(f"  {i}: {device['name']} - {device['max_output_channels']} channels")
                    if "tci" in device["name"].lower():
                        print(f"    Found TCI device: {device['name']}")
                        device_index = i
                        break
            
            # If still not found, try to find any device with 2+ channels
            if device_index is None:
                devices = sd.query_devices()
                for i, device in enumerate(devices):
                    if device["max_output_channels"] >= 2 and "tci" in device["name"].lower():
                        print(f"Found TCI device by channel check: {device['name']}")
                        device_index = i
                        break
            
            # If still not found, try using the pulse device
            if device_index is None:
                devices = sd.query_devices()
                for i, device in enumerate(devices):
                    if "pulse" in device["name"].lower() and device["max_output_channels"] >= 2:
                        print(f"Using pulse device as fallback: {device['name']}")
                        device_index = i
                        break
            
            if device_index is None:
                # List available devices for debugging
                self.audio_device_manager.list_audio_devices()
                raise RuntimeError("Virtual audio output tci_rx not found. Please check PulseAudio configuration.")
            
            # Start streaming
            asyncio.run(self._start_audio_stream(device_index))

        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.is_running = False
            self.root.after(0, lambda: self.gui.set_button_states(False))
            self.root.after(0, lambda: self.gui.update_status("Error", "red"))

    async def _start_audio_stream(self, device_index: int) -> None:
        """Start the audio streaming loop."""
        # Update monitor state from GUI
        self.audio_monitor.enabled = self.gui.is_monitor_enabled()
        
        # Connect to TCI server
        connected = await self.tci_client.connect()
        if not connected:
            raise RuntimeError("Failed to connect to TCI server")

        print("TCI connected and receiving audio")

        # Start streaming
        await self.audio_streamer.stream(self.tci_client, device_index)

        # Close connection when done
        await self.tci_client.close()
    
    def cleanup(self) -> None:
        """Cleanup resources on application exit."""
        try:
            self.stop_flux()
            self.audio_device_manager.cleanup_devices()
        except Exception as e:
            print(f"Cleanup error: {e}")
        finally:
            self.root.quit()
            self.root.destroy()

def main():
    """Main entry point."""
    root = tk.Tk()
    app = TCIAudioApp(root)

    # Handle window close
    root.protocol("WM_DELETE_WINDOW", app.cleanup)

    root.mainloop()


if __name__ == "__main__":
    main()
            
