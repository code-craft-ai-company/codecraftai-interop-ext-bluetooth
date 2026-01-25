import logging
from .coordinator import BluetoothCoordinator

logger = logging.getLogger(__name__)

class BluetoothDevice:
    """
    Represents a specific Bluetooth device.
    """
    def __init__(self, address: str, coordinator: BluetoothCoordinator):
        self.address = address
        self.coordinator = coordinator
        self.connection = None

    async def connect(self):
        """
        Connects to the device.
        """
        logger.info(f"Connecting to device {self.address}")
        if not self.coordinator.device:
             raise RuntimeError("Coordinator not initialized. Call startup() on coordinator first.")

        # self.coordinator.device.connect usually returns a Connection object
        self.connection = await self.coordinator.device.connect(self.address)
        logger.info(f"Connected to {self.address}")
        return self.connection

    async def disconnect(self):
        """
        Disconnects from the device.
        """
        if self.connection:
            logger.info(f"Disconnecting from {self.address}")
            await self.connection.disconnect()
            self.connection = None

    async def pair(self):
        """
        Pairs with the device.
        """
        if not self.connection:
            await self.connect()

        logger.info(f"Pairing with {self.address}")
        # Assuming Connection object has pair() method or similar in Bumble
        await self.connection.pair()
