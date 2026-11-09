import tkinter as tk
from tkinter import messagebox
import asyncio
import numpy as np
import sounddevice as sd
import websockets
import subprocess
import threading

# Variables globales
URI = ""
DEVICE = None
output_stream = None

# Fonction pour se connecter au serveur TCI
async def connect_to_tci(uri):
    global DEVICE, output_stream
    devices = sd.query_devices()
    DEVICE = next(
        (
            i for i, d in enumerate(devices)
            if d["name"] == "tci_rx"
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
        messagebox.showinfo("Info", "Flux audio arrêté")

# Fonction pour quitter l'application
def quit_app():
    root.destroy()

# Fonction pour se connecter au serveur TCI
def connect():
    global URI
    URI = ip_entry.get()
    if not URI:
        messagebox.showerror("Erreur", "Veuillez entrer une adresse IP")
        return
    threading.Thread(target=lambda: asyncio.run(connect_to_tci(URI))).start()

# Interface graphique
root = tk.Tk()
root.title("TCI Audio Control")

ip_label = tk.Label(root, text="Adresse IP du serveur TCI:")
ip_label.pack()

ip_entry = tk.Entry(root)
ip_entry.pack()

connect_button = tk.Button(root, text="Connecter", command=connect)
connect_button.pack()

stop_button = tk.Button(root, text="Stop", command=stop_audio)
stop_button.pack()

quit_button = tk.Button(root, text="Quitter", command=quit_app)
quit_button.pack()

root.mainloop()
