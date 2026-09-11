"""
    Tests for :class:`ccai.interop.bluetooth.bluetoothcoordinator.BluetoothCoordinator`.

    The coordinator runs for real (its own loop thread, a real bumble ``Device``); only the
    transport is redirected onto an in-process bumble virtual controller.
"""

import asyncio
import threading
from typing import Any
from unittest.mock import patch

from bumble.device import Device

import ccai.interop.bluetooth.bluetoothcoordinator as bluetoothcoordinator_module
from ccai.interop.bluetooth.bluetoothcoordinator import BluetoothCoordinator

from ccai.testshared.bluetooth.virtualbluetoothlink import VIRTUAL_TRANSPORT_ADDRESS, VirtualBluetoothLink

LOOP_THREAD_NAME = "am-bt-coordinator-loop"


async def report_thread_name(marker: Any) -> Any:
    """
        Coroutine used to check where ``submit_coroutine`` runs its work.

        :param marker: A value to echo back.

        :returns: The current thread name and the marker.
    """
    thread_name = threading.current_thread().name
    result = (thread_name, marker)
    return result


async def raise_transport_failure(name: str) -> Any:
    """
        Replacement for ``open_transport_or_link`` that models an adapter that cannot be opened.

        :param name: The requested transport address.

        :raises: OSError
    """
    raise OSError("cannot open transport {!r}".format(name))


def test_coordinator_submit_before_startup_raises() -> None:
    """
        Submitting a coroutine before ``startup()`` is a usage error and raises ``RuntimeError``.
    """
    coordinator = BluetoothCoordinator(transport_address=VIRTUAL_TRANSPORT_ADDRESS)
    coro = report_thread_name("unused")

    raised = None
    try:
        coordinator.submit_coroutine(coro)
    except RuntimeError as rerr:
        raised = rerr
    finally:
        coro.close()

    if raised is None:
        raise AssertionError("submit_coroutine() before startup() did not raise RuntimeError")

    return


def test_coordinator_shutdown_without_startup_is_safe() -> None:
    """
        Shutting down a coordinator that was never started is a no-op.
    """
    coordinator = BluetoothCoordinator(transport_address=VIRTUAL_TRANSPORT_ADDRESS)

    coordinator.shutdown()

    if coordinator._running is not False:
        raise AssertionError("A never-started coordinator should not report running")

    if coordinator.device is not None:
        raise AssertionError("A never-started coordinator should have no device")

    return


def test_coordinator_startup_powers_on_device_and_runs_coroutines_on_loop_thread() -> None:
    """
        ``startup()`` opens the transport, builds a powered-on bumble device, and ``submit_coroutine``
        runs work on the coordinator's own loop thread and hands the result back.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()

    with link.patch_coordinator_transport():
        coordinator.startup()
        try:
            if link.opened_transport_names != [VIRTUAL_TRANSPORT_ADDRESS]:
                raise AssertionError("Expected the configured transport to be opened once, got {!r}".format(link.opened_transport_names))

            if not isinstance(coordinator.device, Device):
                raise AssertionError("startup() should build a bumble Device, got {!r}".format(coordinator.device))

            if coordinator.device.powered_on is not True:
                raise AssertionError("startup() should leave the device powered on")

            thread_name, marker = coordinator.submit_coroutine(report_thread_name("echo"))

            if thread_name != LOOP_THREAD_NAME:
                raise AssertionError("Coroutine ran on thread {!r}, expected {!r}".format(thread_name, LOOP_THREAD_NAME))

            if marker != "echo":
                raise AssertionError("submit_coroutine() did not return the coroutine's result")
        finally:
            coordinator.shutdown()

    return


def test_coordinator_startup_is_idempotent() -> None:
    """
        A second ``startup()`` keeps the running loop, thread and device instead of replacing them.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()

    with link.patch_coordinator_transport():
        coordinator.startup()
        try:
            first_loop = coordinator._loop
            first_thread = coordinator._loop_thread
            first_device = coordinator.device

            coordinator.startup()

            if coordinator._loop is not first_loop:
                raise AssertionError("Second startup() replaced the event loop")

            if coordinator._loop_thread is not first_thread:
                raise AssertionError("Second startup() replaced the loop thread")

            if coordinator.device is not first_device:
                raise AssertionError("Second startup() replaced the device")

            if len(link.opened_transport_names) != 1:
                raise AssertionError("Second startup() opened another transport: {!r}".format(link.opened_transport_names))
        finally:
            coordinator.shutdown()

    return


def test_coordinator_startup_failure_shuts_down_and_reraises() -> None:
    """
        When the transport cannot be opened the error propagates, the loop thread is torn down and
        the coordinator is back to its not-running state.
    """
    coordinator = BluetoothCoordinator(transport_address="usb:99")

    raised = None
    with patch.object(bluetoothcoordinator_module, "open_transport_or_link", raise_transport_failure):
        try:
            coordinator.startup()
        except OSError as oserr:
            raised = oserr

    if raised is None:
        raise AssertionError("startup() should propagate the transport failure")

    if coordinator._running is not False:
        raise AssertionError("A failed startup should leave the coordinator not running")

    if coordinator._loop is not None or coordinator._loop_thread is not None:
        raise AssertionError("A failed startup should tear down the loop and its thread")

    if coordinator.device is not None:
        raise AssertionError("A failed startup should leave no device")

    return


def test_coordinator_scanning_toggles_virtual_device() -> None:
    """
        ``start_scanning`` and ``stop_scanning`` drive the bumble device's scanning state.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()

    with link.patch_coordinator_transport():
        coordinator.startup()
        try:
            if coordinator.device.is_scanning is not False:
                raise AssertionError("Device should not be scanning right after startup")

            coordinator.start_scanning()
            if coordinator.device.is_scanning is not True:
                raise AssertionError("start_scanning() should leave the device scanning")

            coordinator.stop_scanning()
            if coordinator.device.is_scanning is not False:
                raise AssertionError("stop_scanning() should leave the device not scanning")
        finally:
            coordinator.shutdown()

    return


def test_coordinator_async_scanning_without_device() -> None:
    """
        Starting a scan before the device exists raises ``RuntimeError``; stopping one is a no-op.
    """
    coordinator = BluetoothCoordinator(transport_address=VIRTUAL_TRANSPORT_ADDRESS)

    raised = None
    try:
        asyncio.run(coordinator._async_start_scanning())
    except RuntimeError as rerr:
        raised = rerr

    if raised is None:
        raise AssertionError("_async_start_scanning() without a device did not raise RuntimeError")

    result = asyncio.run(coordinator._async_stop_scanning())
    if result is not None:
        raise AssertionError("_async_stop_scanning() without a device should return None")

    return


def test_coordinator_shutdown_clears_device_loop_and_thread() -> None:
    """
        ``shutdown()`` powers the device off, drops the transport and device, stops the loop and joins its thread.
    """
    link = VirtualBluetoothLink()
    coordinator = link.create_coordinator()

    with link.patch_coordinator_transport():
        coordinator.startup()
        device = coordinator.device
        loop_thread = coordinator._loop_thread

        coordinator.shutdown()

    if device.powered_on is not False:
        raise AssertionError("shutdown() should power the device off")

    if coordinator.device is not None or coordinator.transport is not None:
        raise AssertionError("shutdown() should drop the device and transport")

    if coordinator._loop is not None or coordinator._loop_thread is not None:
        raise AssertionError("shutdown() should drop the loop and thread")

    if loop_thread.is_alive() is not False:
        raise AssertionError("shutdown() should stop the loop thread")

    if coordinator._running is not False:
        raise AssertionError("shutdown() should leave the coordinator not running")

    return
