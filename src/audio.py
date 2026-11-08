"""Audio streaming and monitoring functionality."""

import asyncio
import threading
import queue
import time
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

# Import configuration directly from the module path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config import (
        AUDIO_SAMPLE_RATE, AUDIO_CHANNELS, AUDIO_DTYPE, AUDIO_BLOCKSIZE,
        AUDIO_QUEUE_MAXSIZE, S9_THRESHOLD, S9_PLUS_THRESHOLD
    )
except ImportError:
    # Fallback for direct execution
    AUDIO_SAMPLE_RATE = 48000
    AUDIO_CHANNELS = 2
    AUDIO_DTYPE = "float32"
    AUDIO_BLOCKSIZE = 0
    AUDIO_QUEUE_MAXSIZE = 10
    S9_THRESHOLD = 50
    S9_PLUS_THRESHOLD = 40


class AudioMonitor:
    """Handles audio monitoring and output."""
    
    def __init__(self, queue_maxsize: int = AUDIO_QUEUE_MAXSIZE):
        self.audio_queue = queue.Queue(maxsize=queue_maxsize)
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.enabled = True
        self._output_stream: Optional[sd.OutputStream] = None
    
    def start_monitoring(self) -> None:
        """Start the monitoring thread."""
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_worker, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring thread."""
        self.stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def queue_audio(self, audio_data: np.ndarray) -> None:
        """Add audio data to the monitoring queue."""
        if self.enabled:
            try:
                self.audio_queue.put_nowait(audio_data)
            except queue.Full:
                pass  # Drop audio data if queue is full
    
    def _monitor_worker(self) -> None:
        """Worker thread for audio monitoring."""
        try:
            default_device = sd.default.device[1]  # Output device
            
            if default_device is None:
                print("Warning: No default audio output device found")
                return

            print(f"Monitoring using default output device: {default_device}")
            
            with sd.OutputStream(
                device=default_device,
                samplerate=AUDIO_SAMPLE_RATE,
                channels=AUDIO_CHANNELS,
                dtype=AUDIO_DTYPE,
                blocksize=1024
            ) as output:
                while not self.stop_event.is_set():
                    try:
                        audio = self.audio_queue.get(timeout=1.0)
                        if self.enabled and audio is not None:
                            output.write(audio)
                        self.audio_queue.task_done()
                    except queue.Empty:
                        continue
                    except Exception as e:
                        if not self.stop_event.is_set():
                            print(f"Monitoring error: {e}")
                        break
                        
        except Exception as e:
            print(f"Monitoring error: {e}")


class AudioStreamer:
    """Handles audio streaming from TCI server."""
    
    def __init__(self, monitor: AudioMonitor, on_s_meter_update: Optional[Callable] = None):
        self.monitor = monitor
        self.on_s_meter_update = on_s_meter_update
        self.is_running = False
        self._output_stream: Optional[sd.OutputStream] = None
    
    def find_tci_device(self) -> Optional[int]:
        """Find the tci_rx audio device."""
        try:
            devices = sd.query_devices()
            print("Available devices:")
            for i, device in enumerate(devices):
                print(f"  {i}: {device['name']} - {device['max_output_channels']} channels")
            
            # Look for tci_rx device (case insensitive)
            for i, device in enumerate(devices):
                if device["name"].lower() == "tci_rx" and device["max_output_channels"] >= 2:
                    print(f"Found tci_rx device at index {i}")
                    return i
            
            # Try alternative names
            for i, device in enumerate(devices):
                if "tci" in device["name"].lower() and device["max_output_channels"] >= 2:
                    print(f"Found TCI device at index {i}: {device['name']}")
                    return i
            
            print("tci_rx device not found")
            return None
        except Exception as e:
            print(f"Error finding devices: {e}")
            return None
    
    async def stream(self, websocket_client, device_index: int) -> None:
        """Main streaming loop."""
        self.is_running = True
        
        devices = sd.query_devices()
        print(f"Using audio device: {device_index} - {devices[device_index]['name']}")

        # Start monitoring
        self.monitor.start_monitoring()

        # Connect to TCI server (already connected in main)
        await websocket_client.start_audio()
        print("TCI connected and receiving audio")
        
        with sd.OutputStream(
            device=device_index,
            samplerate=AUDIO_SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            dtype=AUDIO_DTYPE,
            blocksize=AUDIO_BLOCKSIZE
        ) as output:
            while self.is_running:
                try:
                    data = await websocket_client.receive(timeout=1.0)

                    if not isinstance(data, bytes):
                        continue

                    if len(data) != 16448:
                        continue

                    # Parse TCI messages for info updates
                    if data.startswith(b"info:"):
                        self._handle_info_message(data)
                    
                    audio = np.frombuffer(data[64:], dtype="<f4")

                    if audio.size != 4096:
                        continue

                    audio = audio.reshape(-1, 2)
                    
                    # Write to main output
                    output.write(audio)
                    
                    # Queue for monitoring
                    self.monitor.queue_audio(audio)

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    if self.is_running:
                        raise RuntimeError(f"Streaming error: {e}")

        # Cleanup
        self.monitor.stop_monitoring()
    
    def _handle_info_message(self, data: bytes) -> None:
        """Handle TCI info message."""
        try:
            from tci import TCIParser
        except ImportError:
            # Fallback for direct execution
            from src.tci import TCIParser
        
        info = TCIParser.parse_info_message(data)
        
        if 's_meter' in info:
            try:
                s_value = int(info['s_meter'])
                if self.on_s_meter_update:
                    self.on_s_meter_update(s_value)
            except ValueError:
                pass
    
    def stop(self) -> None:
        """Stop streaming."""
        self.is_running = False
