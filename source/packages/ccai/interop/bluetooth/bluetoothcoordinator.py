import logging
import asyncio
import threading
from concurrent.futures import Future
from bumble.device import Device
from bumble.transport import open_transport_or_link

logger = logging.getLogger(__name__)

class BluetoothCoordinator:
    """
    Coordinator for Bluetooth operations using Bumble.
    Manages its own background thread and asyncio loop to provide a synchronous API.
    """
    def __init__(self, transport_address="usb:0", device_config=None):
        self.transport_address = transport_address
        self.device_config = device_config or {
            "name": "MojoBluetooth",
            "address": "F0:F1:F2:F3:F4:F5"
        }
        self.device = None
        self.transport = None

        self._loop = None
        self._loop_thread = None
        self._running = False

    def startup(self):
        """
        Starts the coordinator and its background loop.
        """
        if self._running:
            return

        logger.info(f"Starting Bluetooth Coordinator with transport: {self.transport_address}")

        self._running = True
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, args=(self._loop,), daemon=True, name="am-bt-coordinator-loop")
        self._loop_thread.start()

        try:
            self.submit_coroutine(self._async_startup())
            logger.info("Bluetooth Coordinator started")
        except Exception as e:
            logger.error(f"Failed to start Bluetooth coordinator: {e}")
            self.shutdown()
            raise

    def shutdown(self):
        """
        Stops the coordinator and its background loop.
        """
        logger.info("Stopping Bluetooth Coordinator")

        if self._loop and self._loop.is_running():
            try:
                self.submit_coroutine(self._async_shutdown())
            except Exception as e:
                logger.warning(f"Error during async shutdown: {e}")

            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=5.0)
            if self._loop_thread.is_alive():
                 logger.warning("Bluetooth Coordinator loop thread did not exit cleanly")

        self._running = False
        self._loop = None
        self._loop_thread = None

    def start_scanning(self, filter_duplicates=True):
        self.submit_coroutine(self._async_start_scanning(filter_duplicates))

    def stop_scanning(self):
        self.submit_coroutine(self._async_stop_scanning())

    def submit_coroutine(self, coro, timeout=10.0):
        """
        Submits a coroutine to the background loop and waits for the result.
        """
        if not self._loop:
            raise RuntimeError("Coordinator loop not running")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def _run_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _async_startup(self):
        # Initialize Bumble device
        name = self.device_config.get("name", "MojoBluetooth")
        address = self.device_config.get("address", "F0:F1:F2:F3:F4:F5")

        self.device = Device(name=name, address=address)

        # Open transport
        self.transport = await open_transport_or_link(self.transport_address)

        self.device.attach_hci_sink(self.transport)
        self.transport.set_packet_sink(self.device)

        await self.device.power_on()

    async def _async_shutdown(self):
        if self.device:
            try:
                await self.device.power_off()
            except Exception as e:
                logger.warning(f"Error powering off device: {e}")

        if self.transport:
            try:
                await self.transport.close()
            except Exception as e:
                logger.warning(f"Error closing transport: {e}")

        self.device = None
        self.transport = None

    async def _async_start_scanning(self, filter_duplicates=True):
        if not self.device:
            raise RuntimeError("Device not initialized")

        logger.info("Starting scanning (async)")
        await self.device.start_scanning(filter_duplicates=filter_duplicates)

    async def _async_stop_scanning(self):
        if not self.device:
            return

        logger.info("Stopping scanning (async)")
        await self.device.stop_scanning()
