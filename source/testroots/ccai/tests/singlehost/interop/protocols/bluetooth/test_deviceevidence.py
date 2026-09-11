"""
    Tests for :class:`ccai.interop.bluetooth.deviceevidence.BluetoothDeviceEvidence`.
"""

from datetime import datetime

from ccai.interop.bluetooth.deviceevidence import BluetoothDeviceEvidence


def test_evidence_defaults_empty_collections_and_stamps_time() -> None:
    """
        Evidence built with only an address and RSSI carries empty UUID and manufacturer
        collections and a timestamp taken at construction.
    """
    before = datetime.now()
    evidence = BluetoothDeviceEvidence(address="AA:BB:CC:DD:EE:FF", rssi=-42)
    after = datetime.now()

    if evidence.name is not None:
        raise AssertionError("Expected no name, got {!r}".format(evidence.name))

    if evidence.service_uuids != []:
        raise AssertionError("Expected an empty service UUID list, got {!r}".format(evidence.service_uuids))

    if evidence.manufacturer_data != {}:
        raise AssertionError("Expected empty manufacturer data, got {!r}".format(evidence.manufacturer_data))

    if evidence.timestamp < before or evidence.timestamp > after:
        raise AssertionError("Timestamp {} is outside the construction interval [{}, {}]".format(evidence.timestamp, before, after))

    return


def test_evidence_as_dict_reports_fields_and_isoformat_timestamp() -> None:
    """
        ``as_dict`` reports the address, RSSI, name, service UUIDs and the timestamp in ISO format.
    """
    stamp = datetime(2025, 3, 4, 5, 6, 7)
    evidence = BluetoothDeviceEvidence(address="AA:BB:CC:DD:EE:FF", rssi=-55, name="Sensor",
                                       service_uuids=["1800", "180A"], timestamp=stamp)

    expected = {
        "address": "AA:BB:CC:DD:EE:FF",
        "rssi": -55,
        "name": "Sensor",
        "service_uuids": ["1800", "180A"],
        "timestamp": "2025-03-04T05:06:07",
    }

    actual = evidence.as_dict()
    if actual != expected:
        raise AssertionError("as_dict mismatch.\nEXPECTED: {!r}\nACTUAL:   {!r}".format(expected, actual))

    return


def test_evidence_str_names_address_rssi_and_name() -> None:
    """
        The string form of evidence carries the address, RSSI and name so log lines identify the device.
    """
    evidence = BluetoothDeviceEvidence(address="AA:BB:CC:DD:EE:FF", rssi=-70, name="Sensor")

    text = str(evidence)

    expected = "<BluetoothDeviceEvidence address=AA:BB:CC:DD:EE:FF rssi=-70 name=Sensor>"
    if text != expected:
        raise AssertionError("str mismatch.\nEXPECTED: {!r}\nACTUAL:   {!r}".format(expected, text))

    return
