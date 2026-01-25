import logging
import asyncio
from .coordinator import BluetoothCoordinator

logger = logging.getLogger(__name__)

class BluetoothPresence:
    """
    Manages Bluetooth presence and discovery.
    """
    def __init__(self, coordinator: BluetoothCoordinator):
        self.coordinator = coordinator
        self.discovered_devices = {}

    async def scan_for_devices(self, timeout=10):
        """
        Scans for devices for a specified duration.
        Returns a list of devices discovered during this scan.
        """
        if not self.coordinator.device:
            raise RuntimeError("Coordinator not initialized. Call startup() on coordinator first.")

        logger.info(f"Scanning for devices for {timeout} seconds")

        current_scan_devices = {}

        def on_advertisement(entry):
            address = str(entry.address)
            # Store in cumulative discovery
            if address not in self.discovered_devices:
                logger.info(f"New device discovered: {address} - {entry}")
            self.discovered_devices[address] = entry

            # Store in current scan
            if address not in current_scan_devices:
                current_scan_devices[address] = entry

        # Register listener
        self.coordinator.device.on('advertisement', on_advertisement)

        try:
            await self.coordinator.start_scanning()
            await asyncio.sleep(timeout)
        finally:
            await self.coordinator.stop_scanning()
            # Unregister listener (if Bumble supports remove_listener, otherwise this might leak or need different handling)
            # Bumble's EventEmitter uses remove_listener
            if hasattr(self.coordinator.device, 'remove_listener'):
                self.coordinator.device.remove_listener('advertisement', on_advertisement)

        return list(current_scan_devices.values())

    def clear_cache(self):
        """
        Clears the cache of discovered devices.
        """
        self.discovered_devices.clear()
        logger.info("Cleared discovered devices cache")
