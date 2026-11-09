import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import numpy as np
import sounddevice as sd
import websockets
import subprocess
import os

# Variables globales
server_ip = "192.168.1.200"
server_port = "50001"
uri = f"ws://{server_ip}:{server_port}"
running = False
process = None
pactl_modules = []

def start_tci_stream():
    global running, process
    if not running:
        running = True
        try:
            # Exécution du script tci_micro.sh dans un thread
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
        async def main():
            try:
                print("Connexion au X6100...")
                async with websockets.connect(uri, max_size=None, ping_interval=20) as ws:
                    print("TCI connecté")
                    await ws.send("audio_start:0;")
                    print("Réception audio RX active")

                    # Flux audio vers la sortie virtuelle
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
            except Exception as e:
                print(f"Erreur de connexion : {e}")

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

def quit_app():
    stop_tci_stream()
    root.quit()

# Création de l'interface graphique
root = tk.Tk()
root.title("TCI Audio Stream")
root.geometry("400x250")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

ttk.Label(frame, text="Adresse IP du serveur TCI :").grid(row=0, column=0, sticky=tk.W)
ip_entry = ttk.Entry(frame, width=20)
ip_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
ip_entry.insert(0, server_ip)

ttk.Button(frame, text="Mettre à jour IP", command=update_ip).grid(row=2, column=0, pady=5)

ttk.Button(frame, text="Connecter", command=connect_to_tci).grid(row=3, column=0, pady=5)
ttk.Button(frame, text="Stop", command=stop_tci_stream).grid(row=4, column=0, pady=5)
ttk.Button(frame, text="Quitter", command=quit_app).grid(row=5, column=0, pady=5)

root.mainloop()
