"""
    Optional hardware test.  It runs only when ``CCAI_BLUETOOTH_TRANSPORT`` names a bumble transport
    for a real adapter (for example ``usb:0`` or ``hci-socket:0``); otherwise it skips.
"""

import os

from ccai.errors.exceptions import SkipError

from ccai.interop.bluetooth.bluetoothcoordinator import BluetoothCoordinator
from ccai.interop.bluetooth.bluetoothpresence import BluetoothPresence

TRANSPORT_VARIABLE = "CCAI_BLUETOOTH_TRANSPORT"


def test_real_adapter_presence_scan() -> None:
    """
        Scans for a few seconds on a real adapter and checks the window closes cleanly.  No device
        is required to be in range; the check is that the adapter opens, scans and shuts down.

        :raises: SkipError when ``CCAI_BLUETOOTH_TRANSPORT`` is not set.
    """
    transport_address = os.environ.get(TRANSPORT_VARIABLE)
    if transport_address is None or len(transport_address.strip()) == 0:
        raise SkipError("Set {} to a bumble transport (for example 'usb:0') to scan with a real adapter.".format(TRANSPORT_VARIABLE))

    coordinator = BluetoothCoordinator(transport_address=transport_address.strip())
    presence = BluetoothPresence(coordinator)

    presence.start()
    try:
        window = presence.discover_devices(window_length=3.0, monitor_interval=0.1)
        closed = window.wait(timeout=10.0)

        if closed is not True:
            raise AssertionError("Search window on {!r} did not close".format(transport_address))

        if window.is_open() is not False:
            raise AssertionError("Search window should be closed after its length elapsed")

        for address, device in window.devices_found.items():
            if device.evidence is None:
                raise AssertionError("Discovered device {!r} has no evidence".format(address))
    finally:
        presence.stop()

    return
