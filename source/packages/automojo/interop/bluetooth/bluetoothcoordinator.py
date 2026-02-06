import logging
import asyncio
from bumble.device import Device
from bumble.transport import open_transport_or_link

logger = logging.getLogger(__name__)

class BluetoothCoordinator:
    """
    Coordinator for Bluetooth operations using Bumble.
    """
    def __init__(self, transport_address="usb:0", device_config=None):
        self.transport_address = transport_address
        self.device_config = device_config or {
            "name": "MojoBluetooth",
            "address": "F0:F1:F2:F3:F4:F5"
        }
        self.device = None
        self.transport = None

    async def startup(self):
        logger.info(f"Starting Bluetooth Coordinator with transport: {self.transport_address}")
        try:
            # Initialize Bumble device
            name = self.device_config.get("name", "MojoBluetooth")
            address = self.device_config.get("address", "F0:F1:F2:F3:F4:F5")

            self.device = Device(name=name, address=address)

            # Open transport
            self.transport = await open_transport_or_link(self.transport_address)
            # Link the device to the transport (Host/Controller interface)
            # Note: Bumble API might require attaching the host to the controller/transport differently
            # dependent on the exact version and usage (Host vs Controller vs Device).
            # For Device class, it usually acts as the Host.
            self.device.attach_hci_sink(self.transport)
            self.transport.set_packet_sink(self.device)

            await self.device.power_on()
            logger.info("Bluetooth Coordinator started")
        except Exception as e:
            logger.error(f"Failed to start Bluetooth transport: {e}")
            raise

    async def shutdown(self):
        logger.info("Stopping Bluetooth Coordinator")
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

    async def start_scanning(self, filter_duplicates=True):
        if not self.device:
            raise RuntimeError("Coordinator not started")

        logger.info("Starting scanning")
        await self.device.start_scanning(filter_duplicates=filter_duplicates)

    async def stop_scanning(self):
        if not self.device:
            return

        logger.info("Stopping scanning")
        await self.device.stop_scanning()
