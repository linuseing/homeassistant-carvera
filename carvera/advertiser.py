import asyncio
import socket

from config import Config

BROADCAST_IP = "255.255.255.255"
UDP_PORT = 3333


async def broadcast_udp(config: Config):
    message = f"{config['name']},{config['homeassistant_ip']},{config['proxy_port']},0".encode()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        try:
            sock.sendto(message, (BROADCAST_IP, UDP_PORT))
        except Exception as e:
            print(f"[UDP] Broadcast error: {e}")

        await asyncio.sleep(config["advertisement_interval"])
