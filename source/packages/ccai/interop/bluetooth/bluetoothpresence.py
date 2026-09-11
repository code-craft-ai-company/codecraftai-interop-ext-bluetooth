
import logging
import threading
import uuid
import weakref
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from bumble.core import AdvertisingData

from .bluetoothcoordinator import BluetoothCoordinator
from .bluetoothsearchwindow import BluetoothSearchWindow
from .bluetoothdevice import BluetoothDevice
from .deviceevidence import BluetoothDeviceEvidence

logger = logging.getLogger(__name__)

# Advertising data structure types that carry lists of service class UUIDs.
SERVICE_UUID_LIST_TYPES = (
    AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,
    AdvertisingData.INCOMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS,
    AdvertisingData.COMPLETE_LIST_OF_32_BIT_SERVICE_CLASS_UUIDS,
    AdvertisingData.INCOMPLETE_LIST_OF_32_BIT_SERVICE_CLASS_UUIDS,
    AdvertisingData.COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS,
    AdvertisingData.INCOMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS,
)


def extract_local_name(data: AdvertisingData) -> Optional[str]:
    """
        Reads the advertised local name out of bumble advertising data, preferring the
        complete local name over the shortened one.

        :param data: The parsed advertising data of an advertisement.

        :returns: The advertised name, or ``None`` when the advertisement carries none.
    """
    name = data.get(AdvertisingData.COMPLETE_LOCAL_NAME)
    if name is None:
        name = data.get(AdvertisingData.SHORTENED_LOCAL_NAME)
    return name


def extract_service_uuids(data: AdvertisingData) -> List[str]:
    """
        Collects every distinct service class UUID advertised in bumble advertising data as a
        hex string (``"1800"`` for 16-bit UUIDs, the full 32 hex digits for 128-bit ones).

        An active scan hands over the advertising packet and the scan response as one
        accumulated advertisement, so the same list can appear twice; each UUID is kept once.

        :param data: The parsed advertising data of an advertisement.

        :returns: The list of advertised service UUIDs, in first-seen order.
    """
    service_uuids = []
    for list_type in SERVICE_UUID_LIST_TYPES:
        for uuid_list in data.get_all(list_type):
            for service_uuid in uuid_list:
                uuid_text = service_uuid.to_hex_str()
                if uuid_text not in service_uuids:
                    service_uuids.append(uuid_text)
    return service_uuids


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
        # Return a shallow copy of the mapping. The BluetoothDevice values are
        # live shared handles -- each holds the coordinator's asyncio loop, a
        # thread, and a lock -- so they must NOT be deep-copied (deepcopy raises
        # TypeError trying to pickle the event loop's context).
        with self._lock:
            devices = dict(self._discovered_devices)
        return devices

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
                # bumble exposes the parsed structures through AdvertisingData.get /
                # get_all; there is no get_local_name() or service_uuids attribute.
                name = extract_local_name(entry.data)
                service_uuids = extract_service_uuids(entry.data)
            
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
