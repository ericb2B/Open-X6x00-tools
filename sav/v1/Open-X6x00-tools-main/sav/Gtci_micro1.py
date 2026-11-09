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
    global running, process
    if running:
        running = False
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
                            # Mettre à jour le buffer audio pour le spectre
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
root.geometry("600x500")

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

# Zone du spectre audio
spectrum_frame = ttk.LabelFrame(frame, text="Spectre Audio", padding="10")
spectrum_frame.grid(row=7, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

# Création de la figure matplotlib pour le spectre
fig, ax = plt.subplots(figsize=(5, 2))
ax.set_title("Spectre Audio")
ax.set_ylabel("Amplitude")
ax.set_xlabel("Fréquence (Hz)")
line, = ax.plot([], [], 'b-', linewidth=1)
ax.set_ylim(0, 1)

canvas = FigureCanvasTkAgg(fig, spectrum_frame)
canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

# Mise à jour du spectre
def update_spectrum():
    global audio_buffer
    if len(audio_buffer) > 0:
        # Calcul du spectre
        fft_data = np.abs(np.fft.fft(audio_buffer))
        freqs = np.fft.fftfreq(len(fft_data), 1/48000)
        line.set_data(freqs[:len(fft_data)//2], fft_data[:len(fft_data)//2])
        ax.set_xlim(0, 10000)  # Limiter à 10kHz
        canvas.draw()
    root.after(100, update_spectrum)  # Mettre à jour toutes les 100ms

# Démarrer l'actualisation du spectre
root.after(100, update_spectrum)

# Configuration de la grille pour l'agrandissement
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
frame.columnconfigure(0, weight=1)
frame.rowconfigure(7, weight=1)

root.mainloop()
