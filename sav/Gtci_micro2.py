import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import numpy as np
import sounddevice as sd
import websockets
import subprocess
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import time

# Variables globales
server_ip = "192.168.1.200"
server_port = "50001"
uri = f"ws://{server_ip}:{server_port}"
running = False
connected = False
process = None
pactl_modules = []
audio_buffer = np.zeros(4096)
audio_thread = None

def start_tci_stream():
    global running, process
    if not running:
        running = True
        try:
            cmd = ["bash", "tci_micro.sh"]
            process = subprocess.Popen(cmd)
            print("Flux TCI démarré.")
        except Exception as e:
            print(f"Erreur au démarrage du flux : {e}")

def stop_tci_stream():
    global running, process, connected
    if running:
        running = False
        connected = False
        update_connection_status()
        try:
            if process and process.poll() is None:
                process.terminate()
                process.wait()
            print("Flux TCI arrêté.")
        except Exception as e:
            print(f"Erreur à l'arrêt du flux : {e}")

def connect_to_tci():
    def run_connection():
        global connected
        async def main():
            try:
                print("Connexion au X6100...")
                async with websockets.connect(uri, max_size=None, ping_interval=20) as ws:
                    connected = True
                    update_connection_status()
                    print("TCI connecté")
                    await ws.send("audio_start:0;")
                    print("Réception audio RX active")

                    devices = sd.query_devices()
                    DEVICE = next(
                        (i for i, d in enumerate(devices)
                         if d["name"] == "tci_rx" and d["max_output_channels"] >= 2),
                        None
                    )
                    if DEVICE is None:
                        raise RuntimeError("Sortie audio tci_rx introuvable")

                    print("Sortie audio :", DEVICE, devices[DEVICE]["name"])

                    with sd.OutputStream(
                            device=DEVICE,
                            samplerate=48000,
                            channels=2,
                            dtype="float32",
                            blocksize=0
                    ) as output:
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
                            # Mettre à jour le buffer audio pour le S-Meter
                            global audio_buffer
                            audio_buffer = np.concatenate([audio_buffer[len(audio):], audio.flatten()[:len(audio)]])

            except Exception as e:
                print(f"Erreur de connexion : {e}")
                connected = False
                update_connection_status()

        asyncio.run(main())

    thread = threading.Thread(target=run_connection)
    thread.daemon = True
    thread.start()

def update_ip():
    global uri
    ip = ip_entry.get()
    if ip:
        uri = f"ws://{ip}:{server_port}"
        print(f"Adresse IP mise à jour : {uri}")

def update_connection_status():
    # Mettre à jour le voyant de connexion
    if connected:
        connection_led.config(bg="green")
        connection_label.config(text="Connecté")
    else:
        connection_led.config(bg="red")
        connection_label.config(text="Déconnecté")

def quit_app():
    stop_tci_stream()
    root.quit()

# Création de l'interface graphique
root = tk.Tk()
root.title("TCI Audio Stream")
root.geometry("500x400")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

# Zone de connexion
ttk.Label(frame, text="Adresse IP du serveur TCI :").grid(row=0, column=0, sticky=tk.W)
ip_entry = ttk.Entry(frame, width=20)
ip_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
ip_entry.insert(0, server_ip)

ttk.Button(frame, text="Mettre à jour IP", command=update_ip).grid(row=2, column=0, pady=5)

# Indicateur de connexion
connection_frame = ttk.Frame(frame)
connection_frame.grid(row=3, column=0, pady=10)

connection_led = tk.Label(connection_frame, width=2, height=1, bg="red")
connection_led.pack(side=tk.LEFT, padx=(0, 5))
connection_label = tk.Label(connection_frame, text="Déconnecté")
connection_label.pack(side=tk.LEFT)

ttk.Button(frame, text="Connecter", command=connect_to_tci).grid(row=4, column=0, pady=5)
ttk.Button(frame, text="Stop", command=stop_tci_stream).grid(row=5, column=0, pady=5)
ttk.Button(frame, text="Quitter", command=quit_app).grid(row=6, column=0, pady=5)

# Zone du S-Meter
smeter_frame = ttk.LabelFrame(frame, text="S-Meter", padding="10")
smeter_frame.grid(row=7, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

# Création de la figure matplotlib pour le S-Meter
fig, ax = plt.subplots(figsize=(5, 2))
ax.set_title("S-Meter")
ax.set_ylabel("Signal Strength")
ax.set_xlabel("S-Units")
ax.set_xlim(0, 10)
ax.set_ylim(0, 1)
ax.grid(True, alpha=0.3)

# Barre S-Meter
smeter_bar = ax.bar([5], [0], width=8, color='red', alpha=0.7)
ax.set_xticks([5])
ax.set_xticklabels(['S-Units'])

canvas = FigureCanvasTkAgg(fig, smeter_frame)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# Mise à jour du S-Meter
def update_smeter():
    global audio_buffer
    if len(audio_buffer) > 0:
        # Calculer le niveau RMS de l'audio
        rms = np.sqrt(np.mean(audio_buffer**2))

        # Conversion en S-units (approximation simple)
        # S-0 = -130 dBm, S-9 = -40 dBm
        # Pour simplifier : S = 10 * log10(rms^2 / 1e-13) - 130
        if rms > 0:
            s_units = min(10, max(0, 10 * np.log10(rms**2 / 1e-13) - 130))
        else:
            s_units = 0

        # Mettre à jour la barre S-Meter
        smeter_bar[0].set_height(s_units)
        ax.set_ylim(0, 10)
        canvas.draw()

    root.after(100, update_smeter)  # Mettre à jour toutes les 100ms

# Démarrer l'actualisation du S-Meter
root.after(100, update_smeter)

# Configuration de la grille pour l'agrandissement
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
frame.columnconfigure(0, weight=1)
frame.rowconfigure(7, weight=1)

root.mainloop()
