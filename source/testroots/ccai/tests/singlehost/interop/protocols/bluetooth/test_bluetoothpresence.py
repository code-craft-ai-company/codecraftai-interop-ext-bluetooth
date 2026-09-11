"""
    Tests for :class:`ccai.interop.bluetooth.bluetoothpresence.BluetoothPresence`.

    The coordinator is a recording stand-in whose ``submit_coroutine`` runs the registration
    coroutine for real, and advertisements are genuine :class:`bumble.device.Advertisement`
    objects, so the evidence path is exercised exactly as bumble drives it.
"""

from typing import Tuple

from ccai.interop.bluetooth.bluetoothpresence import BluetoothPresence

from ccai.testshared.bluetooth.advertisements import make_advertisement
from ccai.testshared.bluetooth.recordingcoordinator import RecordingBumbleDevice, RecordingCoordinator

PEER_ADDRESS = "AA:BB:CC:DD:EE:01"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:02"

# bumble keys public addresses with a type qualifier.
PEER_KEY = PEER_ADDRESS + "/P"
OTHER_KEY = OTHER_ADDRESS + "/P"


def make_started_presence() -> Tuple[BluetoothPresence, RecordingCoordinator, RecordingBumbleDevice]:
    """
        Builds a presence manager over a recording coordinator and starts it.

        :returns: The started presence, its coordinator and the coordinator's stand-in device.
    """
    device = RecordingBumbleDevice()
    coordinator = RecordingCoordinator(device=device)
    presence = BluetoothPresence(coordinator)
    presence.start()
    return presence, coordinator, device


def test_presence_start_registers_listener_and_scans_once() -> None:
    """
        Starting twice starts the coordinator once, registers one ``'advertisement'`` listener
        through the registration coroutine, and starts scanning once.
    """
    presence, coordinator, device = make_started_presence()
    try:
        presence.start()

        if presence.is_running is not True:
            raise AssertionError("Presence should report running after start()")

        if coordinator.startup_calls != 1:
            raise AssertionError("Coordinator startup expected once, got {}".format(coordinator.startup_calls))

        listeners = device.listeners.get("advertisement", [])
        if len(listeners) != 1:
            raise AssertionError("Expected exactly one advertisement listener, got {}".format(len(listeners)))

        if listeners[0] != presence._on_advertisement:
            raise AssertionError("The registered listener should be BluetoothPresence._on_advertisement")

        if coordinator.start_scanning_calls != 1:
            raise AssertionError("Scanning expected to start once, got {}".format(coordinator.start_scanning_calls))

        if "BluetoothPresence._register_callback_and_scan" not in coordinator.submitted_coroutines:
            raise AssertionError("Registration coroutine was not submitted: {!r}".format(coordinator.submitted_coroutines))
    finally:
        presence.stop()

    return


def test_presence_stop_is_idempotent() -> None:
    """
        Stopping before starting does nothing; stopping twice after starting stops scanning and
        shuts the coordinator down exactly once.
    """
    device = RecordingBumbleDevice()
    coordinator = RecordingCoordinator(device=device)
    presence = BluetoothPresence(coordinator)

    presence.stop()
    if coordinator.shutdown_calls != 0:
        raise AssertionError("stop() before start() should not shut the coordinator down")

    presence.start()
    presence.stop()
    presence.stop()

    if presence.is_running is not False:
        raise AssertionError("Presence should not report running after stop()")

    if coordinator.stop_scanning_calls != 1:
        raise AssertionError("stop_scanning expected once, got {}".format(coordinator.stop_scanning_calls))

    if coordinator.shutdown_calls != 1:
        raise AssertionError("shutdown expected once, got {}".format(coordinator.shutdown_calls))

    return


def test_presence_start_failure_resets_running_and_reraises() -> None:
    """
        When the coordinator fails to start, the error propagates and the presence is left not running,
        so a later start can be attempted.
    """
    coordinator = RecordingCoordinator(device=RecordingBumbleDevice(), startup_error=OSError("no adapter"))
    presence = BluetoothPresence(coordinator)

    raised = None
    try:
        presence.start()
    except OSError as oserr:
        raised = oserr

    if raised is None:
        raise AssertionError("start() should propagate the coordinator's startup error")

    if presence.is_running is not False:
        raise AssertionError("Presence should not report running after a failed start")

    if len(coordinator.submitted_coroutines) != 0:
        raise AssertionError("No registration should be attempted after a failed startup")

    return


def test_presence_discover_devices_requires_running() -> None:
    """
        Opening a search window before ``start()`` is a usage error and raises ``RuntimeError``.
    """
    presence = BluetoothPresence(RecordingCoordinator(device=RecordingBumbleDevice()))

    raised = None
    try:
        presence.discover_devices(window_length=0.1)
    except RuntimeError as rerr:
        raised = rerr

    if raised is None:
        raise AssertionError("discover_devices() before start() did not raise RuntimeError")

    return


def test_on_advertisement_builds_evidence_from_bumble_advertisement() -> None:
    """
        A bumble advertisement becomes a cached device whose evidence carries the qualified address,
        RSSI, the advertised local name and the advertised service UUIDs as hex strings.
    """
    presence, coordinator, device = make_started_presence()
    try:
        advertisement = make_advertisement(PEER_ADDRESS, rssi=-63, local_name="Sensor",
                                           service_uuids=["1800", "180A", "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"])
        delivered = device.emit_advertisement(advertisement)
        if delivered != 1:
            raise AssertionError("Expected one listener to receive the advertisement, got {}".format(delivered))

        discovered = presence.discovered_devices
        if list(discovered.keys()) != [PEER_KEY]:
            raise AssertionError("Expected {!r} in discovered_devices, got {!r}".format(PEER_KEY, list(discovered.keys())))

        found = discovered[PEER_KEY]
        if found.address != PEER_KEY:
            raise AssertionError("Device address mismatch: {!r}".format(found.address))

        evidence = found.evidence
        if evidence is None:
            raise AssertionError("Discovered device has no evidence")

        if evidence.address != PEER_KEY:
            raise AssertionError("Evidence address mismatch: {!r}".format(evidence.address))

        if evidence.rssi != -63:
            raise AssertionError("Evidence RSSI mismatch: {!r}".format(evidence.rssi))

        if evidence.name != "Sensor":
            raise AssertionError("Evidence name mismatch: {!r}".format(evidence.name))

        expected_uuids = ["1800", "180A", "6E400001B5A3F393E0A9E50E24DCCA9E"]
        if evidence.service_uuids != expected_uuids:
            raise AssertionError("Evidence UUIDs mismatch.\nEXPECTED: {!r}\nACTUAL:   {!r}".format(expected_uuids, evidence.service_uuids))
    finally:
        presence.stop()

    return


def test_on_advertisement_without_name_leaves_name_unset() -> None:
    """
        An advertisement that carries no local name yields evidence with ``name`` set to ``None``
        and no service UUIDs.
    """
    presence, coordinator, device = make_started_presence()
    try:
        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-80))

        evidence = presence.discovered_devices[PEER_KEY].evidence
        if evidence.name is not None:
            raise AssertionError("Expected no name, got {!r}".format(evidence.name))

        if evidence.service_uuids != []:
            raise AssertionError("Expected no service UUIDs, got {!r}".format(evidence.service_uuids))
    finally:
        presence.stop()

    return


def test_on_advertisement_resighting_keeps_device_and_refreshes_evidence() -> None:
    """
        Seeing the same address again keeps the cached device object and replaces its evidence
        with the newer sighting (newer RSSI and a later timestamp).
    """
    presence, coordinator, device = make_started_presence()
    try:
        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-70, local_name="Sensor"))
        first_device = presence.discovered_devices[PEER_KEY]
        first_evidence = first_device.evidence

        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-40, local_name="Sensor"))
        second_device = presence.discovered_devices[PEER_KEY]
        second_evidence = second_device.evidence

        if second_device is not first_device:
            raise AssertionError("Re-sighting should reuse the cached device object")

        if second_evidence is first_evidence:
            raise AssertionError("Re-sighting should replace the evidence object")

        if second_evidence.rssi != -40:
            raise AssertionError("Refreshed evidence should carry the new RSSI, got {}".format(second_evidence.rssi))

        if second_evidence.timestamp < first_evidence.timestamp:
            raise AssertionError("Refreshed evidence timestamp went backwards")

        if len(presence.discovered_devices) != 1:
            raise AssertionError("Re-sighting should not add a second cache entry")
    finally:
        presence.stop()

    return


def test_on_advertisement_feeds_open_windows_only() -> None:
    """
        A sighting is handed to every open window but not to a window that already completed.
    """
    presence, coordinator, device = make_started_presence()
    try:
        completed_window = presence.discover_devices(limit_to=[PEER_ADDRESS], window_length=5.0, monitor_interval=0.02)
        open_window = presence.discover_devices(window_length=5.0, monitor_interval=0.02)

        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-50))
        closed = completed_window.wait(timeout=2.0)
        if closed is not True:
            raise AssertionError("Limited window did not complete after its hint was sighted")

        device.emit_advertisement(make_advertisement(OTHER_ADDRESS, rssi=-50))

        if OTHER_KEY in completed_window.devices_found:
            raise AssertionError("A completed window should not receive later sightings")

        open_found = open_window.devices_found
        if set(open_found.keys()) != {PEER_KEY, OTHER_KEY}:
            raise AssertionError("Open window should have both sightings, got {!r}".format(list(open_found.keys())))
    finally:
        presence.stop()

    return


def test_discover_devices_limit_to_completes_window_on_match() -> None:
    """
        ``discover_devices(limit_to=[...])`` returns a window that completes when the hinted
        address is sighted and reports the match under the caller's bare address.
    """
    presence, coordinator, device = make_started_presence()
    try:
        window = presence.discover_devices(limit_to=[PEER_ADDRESS], window_length=5.0, monitor_interval=0.02)

        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-50, local_name="Sensor"))

        closed = window.wait(timeout=2.0)
        if closed is not True:
            raise AssertionError("Window did not close after the hinted device was sighted")

        if window.is_active() is not False:
            raise AssertionError("Window should not be active after completing")

        matching = window.matching_devices
        if list(matching.keys()) != [PEER_ADDRESS]:
            raise AssertionError("Expected the hint as the matching key, got {!r}".format(list(matching.keys())))

        if matching[PEER_ADDRESS].evidence.name != "Sensor":
            raise AssertionError("Matching device should carry the sighting's evidence")
    finally:
        presence.stop()

    return


def test_discover_devices_window_length_expires_without_sightings() -> None:
    """
        A window whose ``window_length`` passes with no sightings closes on its own with nothing found.
    """
    presence, coordinator, device = make_started_presence()
    try:
        window = presence.discover_devices(limit_to=[PEER_ADDRESS], window_length=0.3, monitor_interval=0.02)

        closed = window.wait(timeout=3.0)
        if closed is not True:
            raise AssertionError("Window did not expire at the end of window_length")

        if window.is_open() is not False:
            raise AssertionError("Expired window should not be open")

        if window.devices_found != {}:
            raise AssertionError("Nothing was advertised, but devices_found is {!r}".format(window.devices_found))
    finally:
        presence.stop()

    return


def test_discovered_devices_returns_snapshot_copy() -> None:
    """
        ``discovered_devices`` hands back a copy of the cache: mutating it does not alter the manager.
    """
    presence, coordinator, device = make_started_presence()
    try:
        device.emit_advertisement(make_advertisement(PEER_ADDRESS, rssi=-50))

        snapshot = presence.discovered_devices
        snapshot.clear()

        if len(presence.discovered_devices) != 1:
            raise AssertionError("Clearing the returned mapping should not empty the manager's cache")
    finally:
        presence.stop()

    return
