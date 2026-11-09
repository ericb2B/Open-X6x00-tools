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
running = False  # Flag to control the audio loop

# Fonction pour arrêter le flux audio
def stop_audio_stream():
    global output_stream, running
    running = False  # Signal the audio loop to stop

    if output_stream:
        try:
            output_stream.close()
        except Exception as e:
            print(f"Erreur lors de la fermeture du flux: {e}")
        output_stream = None

# Fonction pour gérer l'arrêt du flux audio
def cleanup():
    global running

    # Signal the audio loop to stop first
    running = False

    # Give it a moment to stop gracefully
    import time
    time.sleep(0.1)

    stop_audio_stream()

    if SINK_MODULE:
        try:
            subprocess.run(["pactl", "unload-module", SINK_MODULE],
                          check=True, capture_output=True, timeout=5)
        except Exception as e:
            print(f"Erreur lors du déchargement de {SINK_MODULE}: {e}")

    if SOURCE_MODULE:
        try:
            subprocess.run(["pactl", "unload-module", SOURCE_MODULE],
                          check=True, capture_output=True, timeout=5)
        except Exception as e:
            print(f"Erreur lors du déchargement de {SOURCE_MODULE}: {e}")

    print("Périphériques virtuels supprimés.")

# Fonction principale pour la connexion et la réception audio
async def connect_to_tci():
    global DEVICE, output_stream, running

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
            while running:  # Check the running flag instead of infinite loop
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
                    continue  # Check running flag again
                except Exception as e:
                    print(f"Erreur dans la boucle audio: {e}")
                    break

# Fonction pour démarrer le flux audio
def start_audio_stream():
    global running

    if running:
        messagebox.showinfo("Info", "Le flux audio est déjà en cours")
        return

    running = True

    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(connect_to_tci())
        except Exception as e:
            print(f"Erreur dans le flux audio: {e}")
            messagebox.showerror("Erreur", f"Erreur dans le flux audio: {e}")

# Interface graphique Tkinter
def create_gui():
    root = tk.Tk()
    root.title("TCI Audio Stream")
    root.geometry("300x150")

    start_button = tk.Button(root, text="Démarrer le flux", command=start_audio_stream,
                            bg="green", fg="white", height=2, width=20)
    start_button.pack(pady=10)

    stop_button = tk.Button(root, text="Arrêter le flux", command=cleanup,
                           bg="red", fg="white", height=2, width=20)
    stop_button.pack(pady=10)

    root.mainloop()

# Initialisation
running = True  # Initialize to allow audio streaming

# Création de l'interface graphique
create_gui()
