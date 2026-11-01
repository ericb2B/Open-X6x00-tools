import asyncio
import numpy as np
import sounddevice as sd
import websockets

URI = "ws://192.168.1.200:50001"

# Recherche automatique de la sortie virtuelle tci_rx
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
    raise RuntimeError("Sortie audio tci_rx introuvable")

print("Sortie audio :", DEVICE, devices[DEVICE]["name"])

async def main():
    print("Connexion au X6100...")

    async with websockets.connect(
        URI,
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

asyncio.run(main())
