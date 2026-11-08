import asyncio
import websockets

URI = "ws://192.168.1.200:50001"

async def main():
    async with websockets.connect(
        URI,
        ping_interval=20,
        max_size=None
    ) as ws:

        print("Connexion TCI établie")

        await ws.send("audio_start:0;")
        print("Demande audio RX envoyée")

        while True:
            data = await ws.recv()

            if isinstance(data, bytes):
                print(f"Audio RX : {len(data)} octets")
            else:
                print("TCI :", data)

asyncio.run(main())
