
import logging
import asyncio
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
    Manages Bluetooth presence and discovery using a background asyncio loop for Bumble interactions,
    providing a synchronous API similar to UpnpPresence.
    """
    def __init__(self, coordinator: BluetoothCoordinator):
        self._coordinator = coordinator
        self._lock = threading.Lock()
        
        self._running = False
        self._loop_thread = None
        self._loop = None
        
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
        Starts the Bluetooth presence manager background thread.
        """
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(target=self._run_async_loop, args=(self._loop,), daemon=True, name="am-bt-presence-loop")
            self._loop_thread.start()
            
            # Initialize coordinator in the loop
            future = asyncio.run_coroutine_threadsafe(self._coordinator.startup(), self._loop)
            try:
                future.result(timeout=10)
            except Exception as e:
                logger.error(f"Failed to start Bluetooth coordinator: {e}")
                self.stop()
                raise
            
            # Start continuous scanning
            asyncio.run_coroutine_threadsafe(self._start_scanning_internal(), self._loop)


    def stop(self):
        """
        Stops the Bluetooth presence manager.
        """
        with self._lock:
            if not self._running:
                return
            self._running = False
        
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._coordinator.shutdown(), self._loop)
            # We don't forcefully close the loop/thread here to avoid issues with pending tasks,
            # but in a real system we might want a cleaner shutdown signal.
            pass

    def _run_async_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    async def _start_scanning_internal(self):
        # Setup callback
        if hasattr(self._coordinator.device, 'on'):
             self._coordinator.device.on('advertisement', self._on_advertisement)
        
        # We start scanning. BluetoothCoordinator currently defaults to LE.
        # If we wanted to support Classic, we'd need to modify how Bumble is configured or called.
        # This implementation assumes the Coordinator handles the details of 'start_scanning'.
        await self._coordinator.start_scanning()

    def _on_advertisement(self, entry):
        """
        Callback from Bumble when an advertisement is received.
        Executed in the asyncio loop thread.
        """
        try:
            address = str(entry.address)
            rssi = getattr(entry, 'rssi', 0)
            
            # Extract basic info from entry if possible
            # Bumble AdvertisingData parsing is complex, doing basic extraction
            name = None
            service_uuids = []
            
            if hasattr(entry, 'data'):
                # Try to get local name
                name = entry.data.get_local_name() if hasattr(entry.data, 'get_local_name') else None
                # Try to get service UUIDs
                # Bumble's AdvertisingData might expose them via a method or property
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
