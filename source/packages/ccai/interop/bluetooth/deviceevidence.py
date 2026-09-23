
"""
    .. module:: bluetoothdeviceevidence
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module containing the BluetoothDeviceEvidence object.
    
    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
    
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Dict, List, Optional, Any
from datetime import datetime

class BluetoothDeviceEvidence:
    """
        A :class:`BluetoothDeviceEvidence` object is used to track evidence of the current state of Bluetooth devices.
    """

    def __init__(self, address: str, rssi: int, name: Optional[str] = None, 
                 service_uuids: Optional[List[str]] = None, 
                 manufacturer_data: Optional[Dict[int, bytes]] = None,
                 timestamp: Optional[datetime] = None):
        """
            Initialize evidence.
        """
        self._address = address
        self._rssi = rssi
        self._name = name
        self._service_uuids = service_uuids or []
        self._manufacturer_data = manufacturer_data or {}
        self._timestamp = timestamp if timestamp else datetime.now()

    @property
    def address(self) -> str:
        return self._address

    @property
    def rssi(self) -> int:
        return self._rssi

    @property
    def name(self) -> Optional[str]:
        return self._name

    @property
    def service_uuids(self) -> List[str]:
        return self._service_uuids
    
    @property
    def manufacturer_data(self) -> Dict[int, bytes]:
        return self._manufacturer_data

    @property
    def timestamp(self) -> datetime:
        return self._timestamp
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "address": self._address,
            "rssi": self._rssi,
            "name": self._name,
            "service_uuids": self._service_uuids,
            "timestamp": self._timestamp.isoformat()
        }

    def __str__(self):
        return f"<BluetoothDeviceEvidence address={self._address} rssi={self._rssi} name={self._name}>"
