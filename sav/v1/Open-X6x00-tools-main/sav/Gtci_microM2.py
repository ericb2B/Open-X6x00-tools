import tkinter as tk
from tkinter import messagebox
import asyncio
import numpy as np
import sounddevice as sd
import websockets
import subprocess
import threading
import os

# Variables globales
URI = "ws://192.168.1.200:50001"
DEVICE = None
output_stream = None
SINK = "tci_rx"
SOURCE = "tci_micro"
SINK_MODULE = ""
SOURCE_MODULE = ""

# Fonction pour se connecter au serveur TCI
async def connect_to_tci(uri):
    global DEVICE, output_stream
    devices = sd.query_devices()
    DEVICE = next(
        (
            i for i, d in enumerate(devices)
            if d["name"] == SINK
            and d["max_output_channels"] >= 2
        ),
        None
    )
    if DEVICE is None:
        messagebox.showerror("Erreur", "Sortie audio tci_rx introuvable")
        return

    print("Sortie audio :", DEVICE, devices[DEVICE]["name"])
    async with websockets.connect(
        uri,
        max_size=None,
        ping_interval=20
    ) as ws:
        print("TCI connecté")
        await ws.send("audio_start:0;")
        print("Réception audio RX active")
        with sd.OutputStream(
            device=DEVICE,
            samplerate=48000,
            channels=2,
            dtype="float32",
            blocksize=0
        ) as output:
            output_stream = output
            while True:
                data = await ws.recv()
                if not isinstance(data, bytes):
                    continue
                if len(data) != 16448:
                    continue
                audio = np.frombuffer(data[64:], dtype="<f4")
                if audio.size != 4096:
                    continue
                audio = audio.reshape(-1, 2)
                output.write(audio)

# Fonction pour arrêter le flux audio
def stop_audio():
    global output_stream
    if output_stream:
        output_stream.close()
        output_stream = None
        cleanup()
        messagebox.showinfo("Information", "Flux audio arrêté")

# Fonction de nettoyage
def cleanup():
    global SINK_MODULE, SOURCE_MODULE
    if SINK_MODULE:
        subprocess.run(["pactl", "unload-module", SINK_MODULE], check=True)
    if SOURCE_MODULE:
        subprocess.run(["pactl", "unload-module", SOURCE_MODULE], check=True)
    print("Périphériques virtuels supprimés.")

# Fonction pour créer les périphériques virtuels
def create_virtual_devices():
    global SINK_MODULE, SOURCE_MODULE
    SINK_MODULE = subprocess.run(
        ["pactl", "load-module", "module-null-sink",
         f"sink_name={SINK}", "rate=48000", "channels=2",
         f"sink_properties=device.description={SINK}"],
        capture_output=True, text=True
    ).stdout.strip()
    SOURCE_MODULE = subprocess.run(
        ["pactl", "load-module", "module-remap-source",
         f"master={SINK}.monitor", f"source_name={SOURCE}",
         f"source_properties=device.description={SOURCE}"],
        capture_output=True, text=True
    ).stdout.strip()
    print("Périphériques virtuels créés.")

# Fonction principale pour démarrer le flux
def start_flux():
    create_virtual_devices()
    threading.Thread(target=lambda: asyncio.run(connect_to_tci(URI))).start()

# Interface graphique
def create_gui():
    root = tk.Tk()
    root.title("TCI Audio Control")

    def on_connect():
        start_flux()

    def on_stop():
        stop_audio()

    def on_exit():
        root.destroy()

    connect_button = tk.Button(root, text="Connecter", command=on_connect)
    connect_button.pack(pady=10)

    stop_button = tk.Button(root, text="Arrêter", command=on_stop)
    stop_button.pack(pady=10)

    exit_button = tk.Button(root, text="Quitter", command=on_exit)
    exit_button.pack(pady=10)

    root.mainloop()

if __name__ == "__main__":
    create_gui()
