import logging
from typing import Optional
from .bluetoothcoordinator import BluetoothCoordinator
from .deviceevidence import BluetoothDeviceEvidence

logger = logging.getLogger(__name__)

class BluetoothDevice:
    """
    Represents a specific Bluetooth device.
    """
    def __init__(self, address: str, coordinator: BluetoothCoordinator):
        self.address = address
        self.coordinator = coordinator
        self.connection = None
        self._evidence: Optional[BluetoothDeviceEvidence] = None

    @property
    def evidence(self) -> Optional[BluetoothDeviceEvidence]:
        return self._evidence

    def update_evidence(self, evidence: BluetoothDeviceEvidence):
        """
        Updates the key evidence for the device (RSSI, name, etc.)
        """
        self._evidence = evidence

    def connect(self):
        """
        Connects to the device.
        """
        logger.info(f"Connecting to device {self.address}")
        # Execute the connection on the coordinator's loop
        self.connection = self.coordinator.submit_coroutine(self._async_connect())
        logger.info(f"Connected to {self.address}")
        return self.connection

    async def _async_connect(self):
        if not self.coordinator.device:
             raise RuntimeError("Coordinator not initialized. Call startup() on coordinator first.")
        return await self.coordinator.device.connect(self.address)

    def disconnect(self):
        """
        Disconnects from the device.
        """
        if self.connection:
            logger.info(f"Disconnecting from {self.address}")
            self.coordinator.submit_coroutine(self._async_disconnect())
            self.connection = None

    async def _async_disconnect(self):
        if self.connection:
            await self.connection.disconnect()

    def pair(self):
        """
        Pairs with the device.
        """
        logger.info(f"Pairing with {self.address}")
        self.coordinator.submit_coroutine(self._async_pair())

    async def _async_pair(self):
        if not self.connection:
            await self._async_connect()
        await self.connection.pair()
