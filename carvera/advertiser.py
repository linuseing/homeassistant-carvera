import asyncio

# Machine configuration
MACHINE_NAME = "SimulatedMachine"
MACHINE_IP = "0.0.0.0"  # Listen on all interfaces
UDP_PORT = 8888  # Port to listen for queries
TCP_PORT = 2222  # Port for "busy" check
IS_BUSY = False  # Set to True to simulate a busy machine

class UDPHandler(asyncio.DatagramProtocol):
    """Handles incoming UDP queries and responds with machine details."""
    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        """Called when the UDP socket is ready."""
        self.transport = transport

    def datagram_received(self, data, addr):
        """Called when a UDP packet is received."""
        response = f"{MACHINE_NAME},{MACHINE_IP},{TCP_PORT},{'1' if IS_BUSY else '0'}"
        print(f"[UDP] Received query from {addr}, responding: {response}")
        if self.transport:
            self.transport.sendto(response.encode(), addr)

async def udp_listener():
    """Listens for UDP queries and responds with machine details."""
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: UDPHandler(),
        local_addr=(MACHINE_IP, UDP_PORT),
    )
    print(f"[UDP] Listening for queries on {MACHINE_IP}:{UDP_PORT}")
    try:
        await asyncio.sleep(3600)  # Keep running
    finally:
        transport.close()

async def tcp_server():
    """Hosts a TCP server to simulate machine availability."""
    if IS_BUSY:
        print(f"[TCP] Machine is busy, not accepting connections.")
        return

    server = await asyncio.start_server(handle_tcp_client, MACHINE_IP, TCP_PORT)
    addr = server.sockets[0].getsockname()
    print(f"[TCP] Listening on {addr}")

    async with server:
        await server.serve_forever()

async def handle_tcp_client(reader, writer):
    """Handles incoming TCP connections."""
    addr = writer.get_extra_info("peername")
    print(f"[TCP] Connection from {addr}")
    await asyncio.sleep(1)  # Simulate some processing
    writer.close()
    await writer.wait_closed()
    print(f"[TCP] Connection closed from {addr}")

async def main():
    """Runs both UDP and TCP servers concurrently."""
    await asyncio.gather(udp_listener(), tcp_server())
