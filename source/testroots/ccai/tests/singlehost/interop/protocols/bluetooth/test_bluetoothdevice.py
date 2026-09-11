"""
    Tests for :class:`ccai.interop.bluetooth.bluetoothdevice.BluetoothDevice` over a recording
    coordinator whose ``submit_coroutine`` runs the device's coroutines for real.
"""

from ccai.interop.bluetooth.bluetoothdevice import BluetoothDevice
from ccai.interop.bluetooth.deviceevidence import BluetoothDeviceEvidence

from ccai.testshared.bluetooth.recordingcoordinator import (
    RecordingBumbleDevice,
    RecordingConnection,
    RecordingCoordinator,
)

PEER_ADDRESS = "AA:BB:CC:DD:EE:01/P"


def test_device_connect_requires_initialized_coordinator() -> None:
    """
        Connecting through a coordinator whose device was never initialised raises ``RuntimeError``
        and leaves the device unconnected.
    """
    coordinator = RecordingCoordinator(device=None)
    device = BluetoothDevice(PEER_ADDRESS, coordinator)

    raised = None
    try:
        device.connect()
    except RuntimeError as rerr:
        raised = rerr

    if raised is None:
        raise AssertionError("connect() without an initialised coordinator did not raise RuntimeError")

    if device.connection is not None:
        raise AssertionError("A failed connect should leave no connection behind")

    return


def test_device_connect_returns_connection_from_coordinator_device() -> None:
    """
        ``connect`` asks the coordinator's device for the peer address and keeps the connection it returns.
    """
    connection = RecordingConnection()
    bumble_device = RecordingBumbleDevice(connection=connection)
    coordinator = RecordingCoordinator(device=bumble_device)
    device = BluetoothDevice(PEER_ADDRESS, coordinator)

    returned = device.connect()

    if returned is not connection:
        raise AssertionError("connect() should return the connection the coordinator device produced")

    if device.connection is not connection:
        raise AssertionError("connect() should keep the connection on the device")

    if bumble_device.connect_calls != [PEER_ADDRESS]:
        raise AssertionError("Expected one connect for {!r}, got {!r}".format(PEER_ADDRESS, bumble_device.connect_calls))

    return


def test_device_disconnect_without_connection_is_noop() -> None:
    """
        Disconnecting a device that never connected submits nothing to the coordinator.
    """
    coordinator = RecordingCoordinator(device=RecordingBumbleDevice())
    device = BluetoothDevice(PEER_ADDRESS, coordinator)

    device.disconnect()

    if len(coordinator.submitted_coroutines) != 0:
        raise AssertionError("disconnect() without a connection should submit nothing, got {!r}".format(coordinator.submitted_coroutines))

    return


def test_device_disconnect_calls_connection_and_clears_it() -> None:
    """
        Disconnecting a connected device disconnects the connection and forgets it.
    """
    connection = RecordingConnection()
    coordinator = RecordingCoordinator(device=RecordingBumbleDevice(connection=connection))
    device = BluetoothDevice(PEER_ADDRESS, coordinator)
    device.connect()

    device.disconnect()

    if connection.disconnect_calls != 1:
        raise AssertionError("Expected one disconnect on the connection, got {}".format(connection.disconnect_calls))

    if device.connection is not None:
        raise AssertionError("disconnect() should clear the connection")

    return


def test_device_pair_connects_first_when_not_connected() -> None:
    """
        Pairing an unconnected device connects first and then pairs over that connection.
    """
    connection = RecordingConnection()
    bumble_device = RecordingBumbleDevice(connection=connection)
    coordinator = RecordingCoordinator(device=bumble_device)
    device = BluetoothDevice(PEER_ADDRESS, coordinator)

    device.pair()

    if bumble_device.connect_calls != [PEER_ADDRESS]:
        raise AssertionError("pair() should connect first, connect calls: {!r}".format(bumble_device.connect_calls))

    if device.connection is not connection:
        raise AssertionError("pair() should keep the connection it opened")

    if connection.pair_calls != 1:
        raise AssertionError("Expected one pair call, got {}".format(connection.pair_calls))

    return


def test_device_pair_reuses_existing_connection() -> None:
    """
        Pairing a connected device pairs over the existing connection without reconnecting.
    """
    connection = RecordingConnection()
    bumble_device = RecordingBumbleDevice(connection=connection)
    coordinator = RecordingCoordinator(device=bumble_device)
    device = BluetoothDevice(PEER_ADDRESS, coordinator)
    device.connect()

    device.pair()

    if len(bumble_device.connect_calls) != 1:
        raise AssertionError("pair() on a connected device should not reconnect, connect calls: {!r}".format(bumble_device.connect_calls))

    if connection.pair_calls != 1:
        raise AssertionError("Expected one pair call, got {}".format(connection.pair_calls))

    return


def test_device_update_evidence_replaces_evidence() -> None:
    """
        A device starts with no evidence; each ``update_evidence`` replaces what it holds.
    """
    device = BluetoothDevice(PEER_ADDRESS, RecordingCoordinator())

    if device.evidence is not None:
        raise AssertionError("A new device should have no evidence")

    first = BluetoothDeviceEvidence(address=PEER_ADDRESS, rssi=-70)
    second = BluetoothDeviceEvidence(address=PEER_ADDRESS, rssi=-40)

    device.update_evidence(first)
    if device.evidence is not first:
        raise AssertionError("update_evidence should store the given evidence")

    device.update_evidence(second)
    if device.evidence is not second:
        raise AssertionError("update_evidence should replace earlier evidence")

    return
