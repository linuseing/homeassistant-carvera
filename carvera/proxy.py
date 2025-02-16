import asyncio
import logging

REMOTE_HOST = '192.168.2.138'  # The remote server's address
REMOTE_PORT = 2222         # The remote server's port
LOCAL_PORT  = 2222         # The local port for the proxy to listen on
RECONNECT_DELAY = 5        # How many seconds to wait before reconnect attempts

class TcpProxy:
    def __init__(self, remote_host, remote_port, local_port, reconnect_delay=5):
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_port  = local_port
        self.reconnect_delay = reconnect_delay

        # Remote server connection (reader/writer)
        self.server_reader = None
        self.server_writer = None

        # Current client connection (reader/writer)
        self.client_reader = None
        self.client_writer = None

        # Tasks for bridging data between client <-> server
        self.client_to_server_task = None
        self.server_to_client_task = None

        # Task in charge of maintaining the server connection
        self.server_connect_task = None

        self.local_server = None

    async def start(self):
        """Start listening locally and initiate a background task to connect to the remote server."""
        # Start listening for incoming client connections
        self.local_server = await asyncio.start_server(
            self.handle_new_client,
            host='0.0.0.0',
            port=self.local_port
        )
        logging.info(f"Local proxy listening on port {self.local_port}")

        # Start the background task to keep the server connection alive
        self.server_connect_task = asyncio.create_task(self.connect_to_server_loop())

        # Run the local server forever (until cancelled)
        async with self.local_server:
            await self.local_server.serve_forever()

    async def connect_to_server_loop(self):
        """Keep trying to connect to the remote server; reconnect on failure."""
        while True:
            try:
                logging.info(f"Attempting to connect to {self.remote_host}:{self.remote_port} ...")
                reader, writer = await asyncio.open_connection(self.remote_host, self.remote_port)
                logging.info(f"Connected to remote server {self.remote_host}:{self.remote_port}")

                self.server_reader, self.server_writer = reader, writer

                # If a client is already connected, start bridging immediately
                if self.client_reader and self.client_writer:
                    self.start_bridging_tasks()

                # Wait until server disconnects or an error happens
                # A simple way is to read() in a loop or just read(1) once. If server closes, read returns b''.
                await self.server_reader.read(1)
                logging.warning("Remote server closed the connection.")
            except Exception as e:
                logging.error(f"Error connecting or reading from server: {e}")

            # Clean up the server side
            await self.cleanup_server_connection()

            # Wait before attempting to reconnect
            logging.info(f"Reconnecting to server in {self.reconnect_delay} seconds...")
            await asyncio.sleep(self.reconnect_delay)

    async def handle_new_client(self, reader, writer):
        """Handle a new incoming client. Drop the old one if necessary."""
        client_addr = writer.get_extra_info('peername')
        logging.info(f"New client connected from {client_addr}")

        # Drop old client if there is one
        if self.client_reader or self.client_writer:
            logging.info("Dropping existing client for the new connection.")
            await self.cleanup_client_connection()

        # Store the new client
        self.client_reader, self.client_writer = reader, writer

        # If we are already connected to server, start bridging data
        if self.server_writer:
            self.start_bridging_tasks()
        else:
            logging.warning("Not connected to remote server yet. Will bridge when server is available.")

        # Block here until the client disconnects (or read 0 bytes)
        try:
            await self.client_reader.read(1)  # Wait until the client closes
        except Exception as e:
            logging.error(f"Error reading from client: {e}")

        logging.info(f"Client {client_addr} disconnected.")
        await self.cleanup_client_connection()

    def start_bridging_tasks(self):
        """Start two tasks to forward data between client <-> server."""
        # Cancel old bridging tasks if they exist
        if self.client_to_server_task:
            self.client_to_server_task.cancel()
        if self.server_to_client_task:
            self.server_to_client_task.cancel()

        # Create fresh tasks
        self.client_to_server_task = asyncio.create_task(
            self.bridge(self.client_reader, self.server_writer)
        )
        self.server_to_client_task = asyncio.create_task(
            self.bridge(self.server_reader, self.client_writer)
        )

    async def bridge(self, reader, writer):
        """
        Continuously read data from `reader` and write to `writer`.
        If `reader` hits EOF or any error occurs, we stop and close `writer`.
        """
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break  # EOF or connection closed
                writer.write(data)
                await writer.drain()
        except asyncio.CancelledError:
            # Task was cancelled (e.g., new client or server disconnected)
            pass
        except Exception as e:
            logging.error(f"Error while bridging: {e}")
        finally:
            # If one side ends, close the writer to signal the other side
            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

    async def cleanup_server_connection(self):
        """Close the connection to the server and cancel bridging tasks from server->client."""
        if self.server_writer:
            try:
                self.server_writer.close()
                await self.server_writer.wait_closed()
            except:
                pass

        self.server_reader = None
        self.server_writer = None

        # Stop bridging tasks to/from the server
        if self.server_to_client_task:
            self.server_to_client_task.cancel()
            self.server_to_client_task = None
        if self.client_to_server_task:
            self.client_to_server_task.cancel()
            self.client_to_server_task = None

    async def cleanup_client_connection(self):
        """Close the connection to the client and cancel bridging tasks from client->server."""
        if self.client_writer:
            try:
                self.client_writer.close()
                await self.client_writer.wait_closed()
            except:
                pass

        self.client_reader = None
        self.client_writer = None

        # Stop bridging tasks to/from the client
        if self.client_to_server_task:
            self.client_to_server_task.cancel()
            self.client_to_server_task = None
        if self.server_to_client_task:
            self.server_to_client_task.cancel()
            self.server_to_client_task = None


async def main():
    logging.basicConfig(level=logging.INFO)
    proxy = TcpProxy(REMOTE_HOST, REMOTE_PORT, LOCAL_PORT, RECONNECT_DELAY)
    await proxy.start()
