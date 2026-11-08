"""Audio device management for TCI Audio Interface."""

import subprocess
import os
import time
import sounddevice as sd


class AudioDeviceManager:
    """Manages virtual audio devices for TCI interface."""
    
    def __init__(self):
        self.devices_created = False
    
    def create_virtual_devices(self) -> None:
        """Create virtual audio devices using PulseAudio."""
        try:
            # Unload any existing modules first
            self.cleanup_devices()
            
            # Create null sink for RX with explicit properties
            result = subprocess.run([
                "pactl", "load-module", "module-null-sink",
                "sink_name=tci_rx",
                "rate=48000",
                "channels=2",
                "channel_map=front-left,front-right",
                "sink_properties=device.description=TCI_RX"
            ], check=True, capture_output=True, text=True)
            
            print(f"Null sink created with output: {result.stdout}")
            
            # Create remap source for microphone
            result = subprocess.run([
                "pactl", "load-module", "module-remap-source",
                "master=tci_rx.monitor",
                "source_name=tci_micro",
                "channels=2",
                "channel_map=front-left,front-right",
                "source_properties=device.description=TCI_Microphone"
            ], check=True, capture_output=True, text=True)
            
            print(f"Remap source created with output: {result.stdout}")
            
            self.devices_created = True
            print("Virtual audio devices created successfully")
            
            # Give some time for devices to be registered
            time.sleep(1)
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to create virtual audio devices: {e.stderr}")
        except Exception as e:
            raise RuntimeError(f"Error creating virtual audio devices: {e}")
    
    def cleanup_devices(self) -> None:
        """Clean up virtual audio devices."""
        try:
            # Try to unload modules by name
            try:
                subprocess.run(["pactl", "unload-module", "module-remap-source"], 
                              capture_output=True, check=False)
            except:
                pass
            
            try:
                subprocess.run(["pactl", "unload-module", "module-null-sink"], 
                              capture_output=True, check=False)
            except:
                pass
                
            self.devices_created = False
            print("Virtual audio devices cleaned up")
        except Exception as e:
            print(f"Warning: Cleanup error: {e}")
    
    def list_audio_devices(self) -> None:
        """List all available audio devices for debugging."""
        try:
            devices = sd.query_devices()
            print("Available audio devices:")
            for i, device in enumerate(devices):
                print(f"  {i}: {device['name']} - {device['max_output_channels']} channels")
        except Exception as e:
            print(f"Error listing devices: {e}")
    
    def verify_device_exists(self, device_name: str) -> bool:
        """Verify if a device exists by name."""
        try:
            devices = sd.query_devices()
            for device in devices:
                if device["name"] == device_name:
                    return True
            return False
        except Exception as e:
            print(f"Error verifying device: {e}")
            return False
    
    def check_pulseaudio_modules(self) -> None:
        """Check what PulseAudio modules are currently loaded."""
        try:
            result = subprocess.run(["pactl", "list", "modules"], 
                                  capture_output=True, text=True)
            print("Loaded PulseAudio modules:")
            print(result.stdout)
        except Exception as e:
            print(f"Error checking pulseaudio modules: {e}")
    
    def get_device_index_by_name(self, device_name: str) -> int:
        """Get device index by name (case insensitive)."""
        try:
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                if device["name"].lower() == device_name.lower():
                    return i
            return -1
        except Exception as e:
            print(f"Error getting device index: {e}")
            return -1
