import asyncio
import struct
import websockets

URI = "ws://192.168.1.200:50001"

async def main():
    async with websockets.connect(URI, max_size=None) as ws:

        await ws.send("audio_start:0;")

        print("Réception TCI active")

        while True:
            data = await ws.recv()

            if isinstance(data, bytes):
                if len(data) < 64:
                    continue

                h = struct.unpack("<16I", data[:64])

                print("\n--- TRAME AUDIO ---")
                print("Taille totale :", len(data))
                print("Receiver      :", h[0])
                print("Sample rate   :", h[1])
                print("Format        :", h[2])
                print("Codec         :", h[3])
                print("CRC           :", h[4])
                print("Samples       :", h[5])
                print("Stream type   :", h[6])
                print("Channels      :", h[7])
                print("Payload       :", len(data) - 64)

                break

asyncio.run(main())
