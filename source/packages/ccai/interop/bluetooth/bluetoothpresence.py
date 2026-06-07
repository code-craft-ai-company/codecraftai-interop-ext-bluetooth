
import logging
import threading
import uuid
import weakref
import copy
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .bluetoothcoordinator import BluetoothCoordinator
from .bluetoothsearchwindow import BluetoothSearchWindow
from .bluetoothdevice import BluetoothDevice
from .deviceevidence import BluetoothDeviceEvidence

logger = logging.getLogger(__name__)

class BluetoothPresence:
    """
    Manages Bluetooth presence and discovery using a background thread (via Coordinator)
    and provides a synchronous, thread-safe API.
    """
    def __init__(self, coordinator: BluetoothCoordinator):
        self._coordinator = coordinator
        self._lock = threading.Lock()
        
        self._running = False
        
        # Data storage
        self._discovered_devices: Dict[str, BluetoothDevice] = {} # Persistent cache
        self._search_windows: Dict[str, weakref.ref] = {}
        
    @property
    def is_running(self) -> bool:
        return self._running
        
    @property
    def discovered_devices(self) -> Dict[str, BluetoothDevice]:
        with self._lock:
            return copy.deepcopy(self._discovered_devices)

    def start(self):
        """
        Starts the Bluetooth presence manager.
        """
        with self._lock:
            if self._running:
                return
            
            self._running = True
            
            # Initialize coordinator
            try:
                self._coordinator.startup()
            except Exception as e:
                logger.error(f"Failed to start Bluetooth coordinator: {e}")
                self._running = False
                raise
            
            # Start continuous scanning
            # We need to register the callback.
            # Ideally this should be done safely on the loop.
            # Using submit_coroutine to register callback is tricky because 'on' is not async usually.
            # However, Bumble 'on' just appends to a list.
            # We can define a coroutine to register it to be safe.
            self._coordinator.submit_coroutine(self._register_callback_and_scan())


    def stop(self):
        """
        Stops the Bluetooth presence manager.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
        
        try:
            self._coordinator.stop_scanning()
            self._coordinator.shutdown()
        except Exception as e:
            logger.warning(f"Error stopping coordinator: {e}")


    async def _register_callback_and_scan(self):
        # Setup callback
        if hasattr(self._coordinator.device, 'on'):
             self._coordinator.device.on('advertisement', self._on_advertisement)
        
        await self._coordinator._async_start_scanning()

    def _on_advertisement(self, entry):
        """
        Callback from Bumble when an advertisement is received.
        Executed in the coordinator's loop thread.
        """
        try:
            address = str(entry.address)
            rssi = getattr(entry, 'rssi', 0)
            
            # Extract basic info from entry if possible
            name = None
            service_uuids = []
            
            if hasattr(entry, 'data'):
                # Try to get local name
                name = entry.data.get_local_name() if hasattr(entry.data, 'get_local_name') else None
                # Try to get service UUIDs
                valid_uuids = entry.data.service_uuids if hasattr(entry.data, 'service_uuids') else []
                service_uuids = [str(u) for u in valid_uuids]
            
            # Create Evidence
            evidence = BluetoothDeviceEvidence(
                address=address,
                rssi=rssi,
                name=name,
                service_uuids=service_uuids
            )

            with self._lock:
                if address not in self._discovered_devices:
                    # New device
                    device = BluetoothDevice(address, self._coordinator)
                    device.update_evidence(evidence)
                    self._discovered_devices[address] = device
                    logger.debug(f"Discovered new Bluetooth device: {address} ({name})")
                else:
                    device = self._discovered_devices[address]
                    device.update_evidence(evidence)
                
                # Notify active search windows
                windows_to_notify = []
                for wid, wref in list(self._search_windows.items()):
                    window = wref()
                    if window is None:
                        del self._search_windows[wid]
                        continue
                    
                    if window.is_open():
                        windows_to_notify.append(window)

            # Notify windows
            for window in windows_to_notify:
                window.add_device(address, device)
                
        except Exception as e:
            logger.error(f"Error handling advertisement: {e}")


    def discover_devices(self, limit_to: List[str]=None, window_length: float = 10.0,
                         monitor_interval: float = 0.5) -> BluetoothSearchWindow:
        """
        Opens a search window for devices.
        Returns a BluetoothSearchWindow.
        """
        if not self._running:
            raise RuntimeError("BluetoothPresence must be running. Call start().")

        start = datetime.now()
        end = start + timedelta(seconds=window_length)
        wid = str(uuid.uuid4())

        window = BluetoothSearchWindow(self, wid, start, end, monitor_interval, limit_to=limit_to)
        
        with self._lock:
            self._search_windows[wid] = weakref.ref(window)
        
        window.start()
        
        return window
