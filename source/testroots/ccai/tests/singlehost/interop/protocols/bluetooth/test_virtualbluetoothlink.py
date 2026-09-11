"""
    Integration tests over bumble's virtual controller and local link: real coordinator, real
    presence manager, real peer devices advertising in-process, no Bluetooth adapter.
"""

from ccai.interop.bluetooth.bluetoothdevice import BluetoothDevice
from ccai.interop.bluetooth.bluetoothpresence import BluetoothPresence

from ccai.testshared.bluetooth.virtualbluetoothlink import VirtualBluetoothLink

PEER_ADDRESS = "AA:BB:CC:DD:EE:01"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:02"


def test_presence_sees_virtual_advertiser() -> None:
    """
        One virtual peer advertises; a presence scan limited to its address completes with evidence
        carrying the advertised name, service UUID and a real RSSI.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()
    presence = BluetoothPresence(coordinator)

    with link.patch_coordinator_transport():
        presence.start()
        try:
            link.add_advertiser(coordinator, PEER_ADDRESS, local_name="PeerOne", service_uuids=["180A"])

            window = presence.discover_devices(limit_to=[PEER_ADDRESS], window_length=10.0, monitor_interval=0.05)
            closed = window.wait(timeout=10.0)

            if closed is not True:
                raise AssertionError("Search window did not close while the virtual peer was advertising")

            matching = window.matching_devices
            if list(matching.keys()) != [PEER_ADDRESS]:
                raise AssertionError("Expected the peer to match, got {!r}; found {!r}".format(list(matching.keys()), list(window.devices_found.keys())))

            evidence = matching[PEER_ADDRESS].evidence
            if evidence.name != "PeerOne":
                raise AssertionError("Evidence name mismatch: {!r}".format(evidence.name))

            if evidence.service_uuids != ["180A"]:
                raise AssertionError("Evidence service UUIDs mismatch: {!r}".format(evidence.service_uuids))

            if not isinstance(evidence.rssi, int):
                raise AssertionError("Evidence RSSI should be an int, got {!r}".format(evidence.rssi))

            if not evidence.address.startswith(PEER_ADDRESS):
                raise AssertionError("Evidence address {!r} should start with {!r}".format(evidence.address, PEER_ADDRESS))
        finally:
            link.remove_peers(coordinator)
            presence.stop()

    return


def test_presence_sees_two_virtual_advertisers() -> None:
    """
        Two virtual peers advertise; a scan limited to both addresses completes with both matched
        and each device's evidence carrying its own name.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()
    presence = BluetoothPresence(coordinator)

    with link.patch_coordinator_transport():
        presence.start()
        try:
            link.add_advertiser(coordinator, PEER_ADDRESS, local_name="PeerOne")
            link.add_advertiser(coordinator, OTHER_ADDRESS, local_name="PeerTwo")

            window = presence.discover_devices(limit_to=[PEER_ADDRESS, OTHER_ADDRESS], window_length=10.0, monitor_interval=0.05)
            closed = window.wait(timeout=10.0)

            if closed is not True:
                raise AssertionError("Search window did not close while both virtual peers were advertising")

            matching = window.matching_devices
            if set(matching.keys()) != {PEER_ADDRESS, OTHER_ADDRESS}:
                raise AssertionError("Expected both peers to match, got {!r}".format(list(matching.keys())))

            if matching[PEER_ADDRESS].evidence.name != "PeerOne":
                raise AssertionError("First peer name mismatch: {!r}".format(matching[PEER_ADDRESS].evidence.name))

            if matching[OTHER_ADDRESS].evidence.name != "PeerTwo":
                raise AssertionError("Second peer name mismatch: {!r}".format(matching[OTHER_ADDRESS].evidence.name))

            if len(presence.discovered_devices) != 2:
                raise AssertionError("Expected two cached devices, got {}".format(len(presence.discovered_devices)))
        finally:
            link.remove_peers(coordinator)
            presence.stop()

    return


def test_device_connects_to_virtual_peer() -> None:
    """
        A device discovered over the virtual link can be connected to and disconnected from through
        the coordinator's device, which the peer observes as a real LE connection.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()
    presence = BluetoothPresence(coordinator)

    with link.patch_coordinator_transport():
        presence.start()
        try:
            peer = link.add_advertiser(coordinator, PEER_ADDRESS, local_name="PeerOne")

            window = presence.discover_devices(limit_to=[PEER_ADDRESS], window_length=10.0, monitor_interval=0.05)
            closed = window.wait(timeout=10.0)
            if closed is not True:
                raise AssertionError("Search window did not close while the virtual peer was advertising")

            device = window.matching_devices[PEER_ADDRESS]
            if not isinstance(device, BluetoothDevice):
                raise AssertionError("matching_devices should hold BluetoothDevice objects, got {!r}".format(device))

            coordinator.stop_scanning()

            connection = device.connect()
            if connection is None:
                raise AssertionError("connect() returned no connection")

            if len(peer.connections) != 1:
                raise AssertionError("Peer should observe one connection, got {}".format(len(peer.connections)))

            device.disconnect()
            if device.connection is not None:
                raise AssertionError("disconnect() should clear the connection")

            if len(coordinator.device.connections) != 0:
                raise AssertionError("Coordinator device should have no connections after disconnect, got {}".format(len(coordinator.device.connections)))
        finally:
            link.remove_peers(coordinator)
            presence.stop()

    return
