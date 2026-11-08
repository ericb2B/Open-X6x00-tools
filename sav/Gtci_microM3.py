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

# Fonction pour arrêter le flux audio
def stop_audio_stream():
    global output_stream
    if output_stream:
        output_stream.close()
        output_stream = None

# Fonction pour gérer l'arrêt du flux audio
def cleanup():
    stop_audio_stream()
    if SINK_MODULE:
        subprocess.run(["pactl", "unload-module", SINK_MODULE])
    if SOURCE_MODULE:
        subprocess.run(["pactl", "unload-module", SOURCE_MODULE])
    print("Périphériques virtuels supprimés.")

# Fonction principale pour la connexion et la réception audio
async def connect_to_tci():
    global DEVICE, output_stream
    devices = sd.query_devices()
    DEVICE = next(
        (i for i, d in enumerate(devices) if d["name"] == SINK and d["max_output_channels"] >= 2),
        None
    )
    if DEVICE is None:
        raise RuntimeError("Sortie audio tci_rx introuvable")
    print("Sortie audio :", DEVICE, devices[DEVICE]["name"])

    async with websockets.connect(URI, max_size=None, ping_interval=20) as ws:
        print("TCI connecté")
        await ws.send("audio_start:0;")
        print("Réception audio RX active")

        with sd.OutputStream(device=DEVICE, samplerate=48000, channels=2, dtype="float32", blocksize=0) as output:
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

# Fonction pour démarrer le flux audio
def start_audio_stream():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(connect_to_tci())

# Interface graphique Tkinter
def create_gui():
    root = tk.Tk()
    root.title("TCI Audio Stream")

    start_button = tk.Button(root, text="Démarrer le flux", command=start_audio_stream)
    start_button.pack(pady=10)

    stop_button = tk.Button(root, text="Arrêter le flux", command=cleanup)
    stop_button.pack(pady=10)

    root.mainloop()

# Création de l'interface graphique
create_gui()
