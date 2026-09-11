"""
    .. module:: virtualbluetoothlink
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: An in-process Bluetooth radio environment built from bumble's virtual controller
               and local link, so coordinator and presence tests run without an adapter.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Any, List, Optional, Sequence
from unittest.mock import patch

from bumble import hci
from bumble.controller import Controller
from bumble.device import Device
from bumble.link import LocalLink
from bumble.transport.common import Transport

import ccai.interop.bluetooth.bluetoothcoordinator as bluetoothcoordinator_module
from ccai.interop.bluetooth.bluetoothcoordinator import BluetoothCoordinator

from ccai.testshared.bluetooth.advertisements import build_advertising_data

# The transport address handed to coordinators that are routed through a virtual link.  The
# value is only descriptive: `open_transport` below ignores it and builds a virtual controller.
VIRTUAL_TRANSPORT_ADDRESS = "virtual:0"

# The address the coordinator's own (scanning) device is given.
SCANNER_ADDRESS = "F0:F1:F2:F3:F4:F5"


class VirtualBluetoothLink:
    """
        Owns one :class:`bumble.link.LocalLink` and hands out virtual controllers attached to it.

        A coordinator whose ``open_transport_or_link`` is patched through :meth:`patch_coordinator_transport`
        gets a controller on this link, and :meth:`add_advertiser` puts peer devices on the same link that
        advertise on demand.  Everything happens in-process on the coordinator's loop thread, so the
        fixture behaves the same on Linux, macOS and Windows.

        bumble controllers must be constructed on a running event loop, which is why peers are created
        through ``coordinator.submit_coroutine``.
    """

    def __init__(self):
        """
            Creates an empty link with no controllers on it.
        """
        self._link = LocalLink()
        self._peers: List[Device] = []
        self._controller_count = 0
        self._opened_transport_names: List[str] = []
        return

    @property
    def opened_transport_names(self) -> List[str]:
        """
            The transport names coordinators asked this link to open, in order.
        """
        names = list(self._opened_transport_names)
        return names

    @property
    def peers(self) -> List[Device]:
        """
            The peer devices currently advertising on the link.
        """
        peers = list(self._peers)
        return peers

    async def open_transport(self, name: str) -> Transport:
        """
            Drop-in replacement for ``bumble.transport.open_transport_or_link``: instead of opening
            hardware it creates a virtual controller on this link and wraps it as a transport.

            :param name: The transport address the coordinator was configured with (recorded, not interpreted).

            :returns: A transport whose source and sink are the new virtual controller.
        """
        self._opened_transport_names.append(name)
        self._controller_count += 1
        controller_name = "virtual-controller-{}".format(self._controller_count)
        controller = Controller(controller_name, link=self._link)
        transport = Transport(controller, controller)
        return transport

    def patch_coordinator_transport(self) -> Any:
        """
            Creates a patcher that routes every coordinator's transport opening through this link.

            :returns: A ``patch.object`` context manager over the coordinator module's ``open_transport_or_link``.
        """
        patcher = patch.object(bluetoothcoordinator_module, "open_transport_or_link", self.open_transport)
        return patcher

    def create_coordinator(self, name: str = "VirtualScanner", address: str = SCANNER_ADDRESS) -> BluetoothCoordinator:
        """
            Creates a coordinator configured for this link.  Start it inside :meth:`patch_coordinator_transport`.

            :param name: The bumble device name for the coordinator's own device.
            :param address: The address for the coordinator's own device.

            :returns: An un-started coordinator.
        """
        device_config = {"name": name, "address": address}
        coordinator = BluetoothCoordinator(transport_address=VIRTUAL_TRANSPORT_ADDRESS, device_config=device_config)
        return coordinator

    def add_advertiser(self, coordinator: BluetoothCoordinator, address: str, local_name: Optional[str] = None,
                       service_uuids: Sequence[str] = ()) -> Device:
        """
            Puts a new peer device on the link and starts it advertising with a public address.

            :param coordinator: A started coordinator; the peer is created on its loop thread.
            :param address: The bare public address the peer advertises from, for example ``"AA:BB:CC:DD:EE:01"``.
            :param local_name: The complete local name to advertise, if any.
            :param service_uuids: Service UUID strings to advertise.

            :returns: The advertising peer device.
        """
        peer = coordinator.submit_coroutine(self._async_add_advertiser(address, local_name, service_uuids))
        return peer

    def remove_peers(self, coordinator: BluetoothCoordinator) -> None:
        """
            Powers off every peer on the link.  Call before the coordinator is shut down.

            :param coordinator: The started coordinator whose loop thread hosts the peers.
        """
        coordinator.submit_coroutine(self._async_remove_peers())
        return

    async def _async_add_advertiser(self, address: str, local_name: Optional[str], service_uuids: Sequence[str]) -> Device:
        """
            Loop-thread half of :meth:`add_advertiser`.
        """
        public_address = hci.Address(address, hci.Address.PUBLIC_DEVICE_ADDRESS)

        self._controller_count += 1
        controller_name = "virtual-peer-{}".format(self._controller_count)
        controller = Controller(controller_name, link=self._link, public_address=public_address)

        device_name = local_name
        if device_name is None:
            device_name = address
        peer = Device.with_hci(device_name, public_address, controller, controller)
        await peer.power_on()

        payload = build_advertising_data(local_name=local_name, service_uuids=service_uuids)
        await peer.start_advertising(advertising_data=payload, own_address_type=hci.OwnAddressType.PUBLIC)

        self._peers.append(peer)
        return peer

    async def _async_remove_peers(self) -> None:
        """
            Loop-thread half of :meth:`remove_peers`.
        """
        while len(self._peers) > 0:
            peer = self._peers.pop()
            await peer.power_off()
        return
