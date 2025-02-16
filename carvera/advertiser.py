import asyncio
import socket


MACHINE_NAME = "proxy"
MACHINE_IP = "192.168.2.124"  # Change to the actual machine IP
TCP_PORT = 2222  # Port for the "busy" check
IS_BUSY = False  # Change to True if the machine should appear busy
BROADCAST_IP = "255.255.255.255"  # Broadcast address
UDP_PORT = 3333  # The port where the detector listens
INTERVAL = 5  # Seconds between broadcasts

async def broadcast_udp():
    """Sends a UDP broadcast packet with machine details."""
    message = f"{MACHINE_NAME},{MACHINE_IP},{TCP_PORT},{'1' if IS_BUSY else '0'}".encode()

    # Create a UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        try:
            sock.sendto(message, (BROADCAST_IP, UDP_PORT))
            print(f"[UDP] Broadcast sent: {message.decode()} → {BROADCAST_IP}:{UDP_PORT}")
        except Exception as e:
            print(f"[UDP] Broadcast error: {e}")

        await asyncio.sleep(INTERVAL)

async def main():
    """Runs the UDP broadcaster."""
    await broadcast_udp()
