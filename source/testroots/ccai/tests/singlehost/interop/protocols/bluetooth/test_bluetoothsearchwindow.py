"""
    Tests for :class:`ccai.interop.bluetooth.bluetoothsearchwindow.BluetoothSearchWindow`.

    The windows are built directly, with a real but un-started :class:`BluetoothPresence` as the
    owner (the window only holds it weakly), so no scanning is involved.
"""

import gc
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from bumble import hci

from ccai.testbase.properties import run_property, strategies

from ccai.interop.bluetooth.bluetoothdevice import BluetoothDevice
from ccai.interop.bluetooth.bluetoothpresence import BluetoothPresence
from ccai.interop.bluetooth.bluetoothsearchwindow import (
    BluetoothSearchWindow,
    BluetoothSearchWindowState,
    normalize_address_hint,
)

from ccai.testshared.bluetooth.recordingcoordinator import RecordingCoordinator

PEER_ADDRESS = "AA:BB:CC:DD:EE:01"
OTHER_ADDRESS = "AA:BB:CC:DD:EE:02"


def make_window(limit_to: Optional[List[str]] = None, window_length: float = 0.4,
                monitor_interval: float = 0.02) -> Tuple[BluetoothSearchWindow, BluetoothPresence]:
    """
        Builds an un-started window owned by an un-started presence manager.

        :param limit_to: Address hints the window waits for, or ``None`` to collect everything.
        :param window_length: Seconds until the window expires.
        :param monitor_interval: Seconds between monitor thread checks.

        :returns: The window and its owning presence (the caller must keep the presence alive).
    """
    coordinator = RecordingCoordinator()
    presence = BluetoothPresence(coordinator)

    start = datetime.now()
    end = start + timedelta(seconds=window_length)
    window = BluetoothSearchWindow(presence, "window-under-test", start, end, monitor_interval, limit_to=limit_to)

    return window, presence


def make_device(address: str) -> BluetoothDevice:
    """
        Builds a device handle keyed by the given address.

        :param address: The address the device is known by.

        :returns: A device attached to a recording coordinator.
    """
    device = BluetoothDevice(address, RecordingCoordinator())
    return device


def test_window_wait_before_start_raises() -> None:
    """
        Waiting on a window that was never started is a usage error and raises ``RuntimeError``.
    """
    window, presence = make_window()

    raised = None
    try:
        window.wait(timeout=0.1)
    except RuntimeError as rerr:
        raised = rerr

    if raised is None:
        raise AssertionError("wait() on an inactive window did not raise RuntimeError")

    if window.is_open() is not True:
        raise AssertionError("An inactive window should still count as open")

    return


def test_window_times_out_when_end_passes() -> None:
    """
        A window with no hints closes with the TIMEOUT state once its end time passes.
    """
    window, presence = make_window(window_length=0.3)
    window.start()

    if window.is_active() is not True:
        raise AssertionError("Window should be active immediately after start()")

    closed = window.wait(timeout=3.0)

    if closed is not True:
        raise AssertionError("wait() should report the window closed before the wait timeout")

    if window.is_active() is not False:
        raise AssertionError("Window should not be active after it expired")

    if window.is_open() is not False:
        raise AssertionError("Window should not be open after it expired")

    if window._window_state != BluetoothSearchWindowState.TIMEOUT:
        raise AssertionError("Expected TIMEOUT state, got {}".format(window._window_state))

    return


def test_window_completes_when_every_hint_is_sighted() -> None:
    """
        A window limited to two addresses completes as soon as both have been added, well before its end.
    """
    window, presence = make_window(limit_to=[PEER_ADDRESS, OTHER_ADDRESS], window_length=5.0)
    window.start()

    first_device = make_device(PEER_ADDRESS)
    second_device = make_device(OTHER_ADDRESS)
    window.add_device(PEER_ADDRESS, first_device)
    window.add_device(OTHER_ADDRESS, second_device)

    closed = window.wait(timeout=2.0)

    if closed is not True:
        raise AssertionError("Window did not close after every hint was sighted")

    if window._window_state != BluetoothSearchWindowState.COMPLETED:
        raise AssertionError("Expected COMPLETED state, got {}".format(window._window_state))

    matching = window.matching_devices
    if set(matching.keys()) != {PEER_ADDRESS, OTHER_ADDRESS}:
        raise AssertionError("Expected both hints in matching_devices, got {!r}".format(list(matching.keys())))

    if matching[PEER_ADDRESS] is not first_device:
        raise AssertionError("matching_devices should hand back the device object that was added")

    return


def test_window_without_hints_collects_devices_until_end() -> None:
    """
        A window with no hints never completes early: it keeps collecting sightings and only
        closes at its end time, with nothing in ``matching_devices``.
    """
    window, presence = make_window(limit_to=None, window_length=0.4)
    window.start()

    device = make_device(PEER_ADDRESS)
    window.add_device(PEER_ADDRESS, device)

    if window.is_open() is not True:
        raise AssertionError("A window without hints should stay open after a sighting")

    closed = window.wait(timeout=3.0)
    if closed is not True:
        raise AssertionError("Window without hints should still close at its end time")

    found = window.devices_found
    if list(found.keys()) != [PEER_ADDRESS]:
        raise AssertionError("Expected the sighted device in devices_found, got {!r}".format(list(found.keys())))

    if window.matching_devices != {}:
        raise AssertionError("A window without hints should have no matching devices")

    return


def test_window_wait_after_close_returns_immediately() -> None:
    """
        Waiting on a window that already closed returns ``True`` without blocking.
    """
    window, presence = make_window(limit_to=[PEER_ADDRESS], window_length=5.0)
    window.start()
    window.add_device(PEER_ADDRESS, make_device(PEER_ADDRESS))
    window.wait(timeout=2.0)

    started = datetime.now()
    closed = window.wait(timeout=5.0)
    elapsed = (datetime.now() - started).total_seconds()

    if closed is not True:
        raise AssertionError("wait() on a closed window should return True")

    if elapsed > 1.0:
        raise AssertionError("wait() on a closed window blocked for {:.2f} seconds".format(elapsed))

    return


def test_window_hint_matches_bumble_qualified_address() -> None:
    """
        A bare address hint matches a sighting keyed by bumble's qualified form (``.../P``), and the
        match is reported under the hint the caller supplied.
    """
    window, presence = make_window(limit_to=[PEER_ADDRESS.lower()], window_length=5.0)
    window.start()

    qualified_key = PEER_ADDRESS + "/P"
    device = make_device(qualified_key)
    window.add_device(qualified_key, device)

    closed = window.wait(timeout=2.0)
    if closed is not True:
        raise AssertionError("Window did not complete for a hint that differs only by qualifier and case")

    matching = window.matching_devices
    if list(matching.keys()) != [PEER_ADDRESS.lower()]:
        raise AssertionError("Match should be keyed by the caller's hint, got {!r}".format(list(matching.keys())))

    if matching[PEER_ADDRESS.lower()] is not device:
        raise AssertionError("Match should hand back the sighted device object")

    return


def test_window_presence_reference_is_weak() -> None:
    """
        The window only references its presence manager weakly, so dropping the manager makes
        ``window.presence`` return ``None`` rather than keeping the manager alive.
    """
    window, presence = make_window()

    if window.presence is not presence:
        raise AssertionError("window.presence should resolve to the owning presence while it is alive")

    del presence
    gc.collect()

    if window.presence is not None:
        raise AssertionError("window.presence should be None once the owning presence is collected")

    return


def test_normalize_address_hint_property() -> None:
    """
        For any 6-byte address, every spelling a caller or bumble might use (upper or lower case,
        surrounding whitespace, with or without the ``/P`` qualifier) normalises to one bare
        upper-case address that equals bumble's own unqualified rendering.
    """

    def check(address_bytes: bytes, lower_case: bool, qualified: bool, padded: bool) -> None:
        address = hci.Address(address_bytes, hci.Address.PUBLIC_DEVICE_ADDRESS)
        canonical = address.to_string(with_type_qualifier=False)

        spelling = canonical
        if lower_case is True:
            spelling = spelling.lower()
        if qualified is True:
            spelling = spelling + "/P"
        if padded is True:
            spelling = "  " + spelling + " "

        normalized = normalize_address_hint(spelling)
        if normalized != canonical:
            raise AssertionError("normalize_address_hint({!r}) gave {!r}, expected {!r}".format(spelling, normalized, canonical))

        qualified_normalized = normalize_address_hint(str(address))
        if qualified_normalized != canonical:
            raise AssertionError("bumble's str(address) {!r} normalised to {!r}, expected {!r}".format(str(address), qualified_normalized, canonical))
        return

    run_property(check, max_examples=100,
                 address_bytes=strategies.binary(min_size=6, max_size=6),
                 lower_case=strategies.booleans(),
                 qualified=strategies.booleans(),
                 padded=strategies.booleans())

    return
