"""
    .. module:: recordingcoordinator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Recording stand-ins for the coordinator and the bumble objects it wraps, for
               tests of BluetoothPresence and BluetoothDevice that need no event loop thread.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

import asyncio
from typing import Any, Callable, Coroutine, Dict, List, Optional


class RecordingConnection:
    """
        Stands in for a bumble connection; counts the disconnect and pair requests it receives.
    """

    def __init__(self):
        """
            Creates a connection with no recorded calls.
        """
        self.disconnect_calls = 0
        self.pair_calls = 0
        return

    async def disconnect(self) -> None:
        """
            Records a disconnect request.
        """
        self.disconnect_calls += 1
        return

    async def pair(self) -> None:
        """
            Records a pairing request.
        """
        self.pair_calls += 1
        return


class RecordingBumbleDevice:
    """
        Stands in for :class:`bumble.device.Device`: records event listener registrations and
        connect requests, and lets a test push an advertisement to the registered listeners.
    """

    def __init__(self, connection: Optional[RecordingConnection] = None):
        """
            :param connection: The object ``connect`` returns; defaults to a fresh :class:`RecordingConnection`.
        """
        self.listeners: Dict[str, List[Callable[[Any], None]]] = {}
        self.connect_calls: List[str] = []
        if connection is None:
            connection = RecordingConnection()
        self.connection = connection
        return

    def on(self, event_name: str, listener: Callable[[Any], None]) -> None:
        """
            Records a listener registration the way bumble's event emitter does.

            :param event_name: The event being listened for, for example ``'advertisement'``.
            :param listener: The callback to register.
        """
        listeners = self.listeners.setdefault(event_name, [])
        listeners.append(listener)
        return

    async def connect(self, address: str) -> RecordingConnection:
        """
            Records a connect request and returns the configured connection.

            :param address: The address that was asked for.

            :returns: The configured connection object.
        """
        self.connect_calls.append(address)
        return self.connection

    def emit_advertisement(self, advertisement: Any) -> int:
        """
            Delivers an advertisement to every ``'advertisement'`` listener, as bumble would.

            :param advertisement: The advertisement object to deliver.

            :returns: The number of listeners that received it.
        """
        listeners = self.listeners.get("advertisement", [])
        for listener in listeners:
            listener(advertisement)
        delivered = len(listeners)
        return delivered


class RecordingCoordinator:
    """
        Stands in for :class:`BluetoothCoordinator` without a background loop thread.  Lifecycle
        calls are counted, and ``submit_coroutine`` runs the submitted coroutine for real with
        ``asyncio.run`` so registration coroutines are exercised rather than swallowed.
    """

    def __init__(self, device: Optional[RecordingBumbleDevice] = None, startup_error: Optional[Exception] = None):
        """
            :param device: The stand-in bumble device exposed as ``coordinator.device``; ``None`` models
                           a coordinator whose device has not been initialised.
            :param startup_error: An exception ``startup`` raises, to model a coordinator that fails to start.
        """
        self.device = device
        self.startup_error = startup_error
        self.startup_calls = 0
        self.shutdown_calls = 0
        self.start_scanning_calls = 0
        self.stop_scanning_calls = 0
        self.submitted_coroutines: List[str] = []
        return

    def startup(self) -> None:
        """
            Records a startup request, raising the configured startup error if there is one.
        """
        self.startup_calls += 1
        if self.startup_error is not None:
            raise self.startup_error
        return

    def shutdown(self) -> None:
        """
            Records a shutdown request.
        """
        self.shutdown_calls += 1
        return

    def start_scanning(self, filter_duplicates: bool = True) -> None:
        """
            Records a synchronous start-scanning request.
        """
        self.start_scanning_calls += 1
        return

    def stop_scanning(self) -> None:
        """
            Records a synchronous stop-scanning request.
        """
        self.stop_scanning_calls += 1
        return

    def submit_coroutine(self, coro: Coroutine[Any, Any, Any], timeout: float = 10.0) -> Any:
        """
            Runs the coroutine to completion on a private event loop and returns its result.

            :param coro: The coroutine object to run.
            :param timeout: Accepted for signature compatibility; the coroutine runs to completion.

            :returns: Whatever the coroutine returned.
        """
        self.submitted_coroutines.append(coro.__qualname__)
        result = asyncio.run(coro)
        return result

    async def _async_start_scanning(self, filter_duplicates: bool = True) -> None:
        """
            Records the scanning start that ``BluetoothPresence`` awaits during registration.
        """
        self.start_scanning_calls += 1
        return
