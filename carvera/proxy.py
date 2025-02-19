import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Optional, Awaitable

MIN_INFO_INTERVAL = 2

logging.basicConfig(level=logging.INFO)


class CnCProxy:

    def __init__(
        self,
        remote_host,
        remote_port,
        local_port,
        reconnect_delay: float = 5.0,
        server_message_callback: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ):
        """Create a new CnCProxy. !Attention: callback should be non-blocking!"""
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.local_port = local_port
        self.reconnect_delay = reconnect_delay

        self.queue_client_to_server = asyncio.Queue()
        self.queue_server_to_client = asyncio.Queue()

        self.server_message_callback = server_message_callback

        self.server_manager_task = None
        self.client_manager_task = None
        self.poll_task = None

        self.last_update = datetime.now()

    async def start(self):
        """Start the proxy: spawn the server-manager and the client-manager tasks."""
        logging.info("Starting proxy...")

        self.server_manager_task = asyncio.create_task(self.server_manager())
        self.client_manager_task = asyncio.create_task(self.client_manager())
        self.poll_task = asyncio.create_task(self.poll_job())

        done, pending = await asyncio.wait(
            [self.server_manager_task, self.client_manager_task],
            return_when=asyncio.FIRST_EXCEPTION,
        )

        for task in pending:
            task.cancel()

    async def server_manager(self):
        """
        Continuously connect (and reconnect) to the remote server.
        Start two tasks per successful connection:
          1) read_from_server() to push data into queue_server_to_client
          2) write_to_server() to consume data from queue_client_to_server
        If the connection is lost, cleanup and retry after RECONNECT_DELAY seconds.
        """
        while True:
            logging.info(
                f"Trying to connect to server {self.remote_host}:{self.remote_port}..."
            )
            try:
                reader, writer = await asyncio.open_connection(
                    self.remote_host, self.remote_port
                )
                logging.info("Connected to remote server.")
            except Exception as e:
                logging.error(f"Failed to connect to server: {e}")
                await asyncio.sleep(self.reconnect_delay)
                continue

            read_task = asyncio.create_task(self.read_from_server(reader))
            write_task = asyncio.create_task(self.write_to_server(writer))

            done, pending = await asyncio.wait(
                [read_task, write_task], return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            writer.close()
            try:
                await writer.wait_closed()
            except:
                pass

            logging.warning("Lost connection to server. Will retry...")
            await asyncio.sleep(self.reconnect_delay)

    async def read_from_server(self, reader: asyncio.StreamReader):
        """
        Continuously read data from the remote server and push it
        into queue_server_to_client for the client side to send.
        """
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    logging.info("Server closed the connection (EOF).")
                    break
                await self.queue_server_to_client.put(data)
                if self.server_message_callback:
                    await self.server_message_callback(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error reading from server: {e}")

    async def write_to_server(self, writer: asyncio.StreamWriter):
        """
        Continuously get data from queue_client_to_server and send it
        to the remote server.
        """
        try:
            while True:
                data = await self.queue_client_to_server.get()
                writer.write(data)
                await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error writing to server: {e}")

    async def client_manager(self):
        """
        Accept incoming connections from local clients.
        Only handle ONE client at a time. If a new client arrives, drop the old one.
        For the active client, start two tasks:
          1) read_from_client() to push data into queue_client_to_server
          2) write_to_client() to consume data from queue_server_to_client
        """
        server = await asyncio.start_server(
            self.handle_new_client, "0.0.0.0", self.local_port
        )
        logging.info(f"Listening for clients on port {self.local_port}")

        async with server:
            await server.serve_forever()

    current_client_read_task = None
    current_client_write_task = None
    current_client_writer = None

    async def handle_new_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        A new client connected. Drop the old client (if any) and spawn tasks for the new one.
        """
        client_addr = writer.get_extra_info("peername")
        logging.info(f"New client connected from {client_addr}")

        await self.drop_current_client()

        self.current_client_writer = writer
        self.current_client_read_task = asyncio.create_task(
            self.read_from_client(reader)
        )
        self.current_client_write_task = asyncio.create_task(
            self.write_to_client(writer)
        )

    async def drop_current_client(self):
        """Cancel tasks and close the currently-active client, if any."""
        tasks = [self.current_client_read_task, self.current_client_write_task]
        for t in tasks:
            if t is not None:
                t.cancel()

        if self.current_client_writer:
            try:
                self.current_client_writer.close()
                await self.current_client_writer.wait_closed()
            except:
                pass

        self.current_client_read_task = None
        self.current_client_write_task = None
        self.current_client_writer = None

    async def read_from_client(self, reader: asyncio.StreamReader):
        """
        Continuously read data from the connected client
        and put it on queue_client_to_server for the server manager.
        """
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                if data == b"?":
                    self.last_update = datetime.now()
                await self.queue_client_to_server.put(data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error reading from client: {e}")
        finally:
            logging.info("Client read task ended.")
            await self.drop_current_client()

    async def write_to_client(self, writer: asyncio.StreamWriter):
        """
        Continuously get data from queue_server_to_client and write
        it to the connected client.
        """
        try:
            while True:
                data = await self.queue_server_to_client.get()
                if writer.is_closing():
                    break
                writer.write(data)
                await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error writing to client: {e}")
        finally:
            logging.info("Client write task ended.")
            await self.drop_current_client()

    async def poll_job(self):
        """Periodically request status info from the machine when last info message is stale."""
        while True:
            await asyncio.sleep(1)
            now = datetime.now()
            if (now - self.last_update).seconds < MIN_INFO_INTERVAL:
                continue
            await self.queue_client_to_server.put(b"?")
            self.last_update = now
