
import time
from unittest.mock import MagicMock, AsyncMock

from automojo.interop.bluetooth.bluetoothpresence import BluetoothPresence
from automojo.interop.bluetooth.bluetoothdevice import BluetoothDevice

def test_bluetooth_presence_discovery():
    """
    Verify that BluetoothPresence can discover devices and populate evidence using a mocked coordinator.
    """
    
    # Mock Coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.startup = AsyncMock()
    mock_coordinator.shutdown = AsyncMock()
    mock_coordinator.start_scanning = AsyncMock()
    
    # Mock Bumble Device on Coordinator
    mock_device_wrapper = MagicMock()
    mock_device_wrapper.on = MagicMock()
    mock_coordinator.device = mock_device_wrapper
    
    # Instantiate Presence
    presence = BluetoothPresence(mock_coordinator)
    
    try:
        presence.start()
        
        # Start Discovery
        window = presence.discover_devices(window_length=2.0)
        
        # Wait a bit for start logic to bind the listener
        time.sleep(1) 
        
        # Verify listener registration
        if not mock_device_wrapper.on.called:
             raise AssertionError("'on' listener not registered on coordinator device")

        args, _ = mock_device_wrapper.on.call_args
        event_name, callback = args
        
        if event_name != 'advertisement':
            raise AssertionError(f"Registered for wrong event: {event_name}")

        # Create fake entry
        class MockEntry:
            address = "AA:BB:CC:DD:EE:FF"
            rssi = -70
            class MockData:
                def get_local_name(self): return "TestDevice"
                service_uuids = ["1800"]
            data = MockData()
            
        # Simulate advertisement
        callback(MockEntry())
        
        # Wait for window processing
        time.sleep(0.5)
        
        found = window.devices_found
        
        # Assertions
        if "AA:BB:CC:DD:EE:FF" not in found:
            raise AssertionError("Device not found in search window results")
            
        dev = found["AA:BB:CC:DD:EE:FF"]
        
        if not dev.evidence:
            raise AssertionError("Device has no evidence")
            
        if dev.evidence.name != "TestDevice":
            raise AssertionError(f"Evidence name mismatch. Expected 'TestDevice', got '{dev.evidence.name}'")
            
        # Wait for window completion
        window.wait(timeout=3.0)
        
        if window.is_active():
            raise AssertionError("Search window did not close after timeout")

    finally:
        presence.stop()
