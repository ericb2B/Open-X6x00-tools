import asyncio
import websockets
import struct
import numpy as np

async def main():
    async with websockets.connect(
        "ws://192.168.1.200:50001",
        max_size=None
    ) as ws:
        await ws.send("audio_start:0;")

        while True:
            data = await ws.recv()

            if isinstance(data, bytes) and len(data) == 16448:
                payload = data[64:]

                print("Taille :", len(payload))

                for fmt, dtype in [
                    ("int16", "<i2"),
                    ("int32", "<i4"),
                    ("float32", "<f4")
                ]:
                    a = np.frombuffer(payload, dtype=dtype)
                    print(
                        fmt,
                        "min =", a.min(),
                        "max =", a.max(),
                        "moyenne =", round(float(a.mean()), 4),
                        "premiers =", a[:10]
                    )
                break

asyncio.run(main())
