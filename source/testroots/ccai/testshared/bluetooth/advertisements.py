"""
    .. module:: advertisements
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers that build real bumble advertisements for the bluetooth tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional, Sequence

from bumble import hci
from bumble.core import AdvertisingData, UUID
from bumble.device import Advertisement


def build_advertising_data(local_name: Optional[str] = None, service_uuids: Sequence[str] = ()) -> bytes:
    """
        Builds the raw advertising data payload a peripheral would put on the air.

        :param local_name: The complete local name to advertise, or ``None`` for no name.
        :param service_uuids: Service UUID strings (``"1800"`` or a full 128-bit UUID); 16-bit and
                              128-bit UUIDs are placed in their own complete-list structures.

        :returns: The advertising data as bytes, ready for ``Device.start_advertising``.
    """
    structures = []

    if local_name is not None:
        structures.append((AdvertisingData.COMPLETE_LOCAL_NAME, local_name.encode("utf-8")))

    short_uuid_bytes = b""
    long_uuid_bytes = b""
    for uuid_text in service_uuids:
        service_uuid = UUID(uuid_text)
        uuid_bytes = bytes(service_uuid)
        if len(uuid_bytes) == 2:
            short_uuid_bytes = short_uuid_bytes + uuid_bytes
        else:
            long_uuid_bytes = long_uuid_bytes + service_uuid.to_bytes(force_128=True)

    if len(short_uuid_bytes) > 0:
        structures.append((AdvertisingData.COMPLETE_LIST_OF_16_BIT_SERVICE_CLASS_UUIDS, short_uuid_bytes))

    if len(long_uuid_bytes) > 0:
        structures.append((AdvertisingData.COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS, long_uuid_bytes))

    advertising_data = AdvertisingData(structures)
    payload = bytes(advertising_data)
    return payload


def make_advertisement(address: str, rssi: int = -60, local_name: Optional[str] = None,
                       service_uuids: Sequence[str] = ()) -> Advertisement:
    """
        Creates the :class:`bumble.device.Advertisement` object bumble hands to ``'advertisement'``
        listeners, exactly as a scan of a public peripheral would produce it.

        :param address: The bare public address of the advertiser, for example ``"AA:BB:CC:DD:EE:01"``.
        :param rssi: The received signal strength to report.
        :param local_name: The complete local name carried in the advertising data, if any.
        :param service_uuids: Service UUID strings carried in the advertising data.

        :returns: A parsed advertisement whose ``str(address)`` carries bumble's ``/P`` qualifier.
    """
    public_address = hci.Address(address, hci.Address.PUBLIC_DEVICE_ADDRESS)
    payload = build_advertising_data(local_name=local_name, service_uuids=service_uuids)
    advertisement = Advertisement(address=public_address, rssi=rssi, data_bytes=payload)
    return advertisement
