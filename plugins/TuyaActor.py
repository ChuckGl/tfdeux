# filename: TuyaActor.py

import logging
import tinytuya
from event import notify, Event
from interfaces import Actor

logger = logging.getLogger(__name__)

def factory(name, settings):
    """Factory function to create a TuyaActor instance."""
    return TuyaActor(name, settings)

class TuyaActor(Actor):
    def __init__(self, name, settings):
        """Initialize the TuyaActor with device-specific settings."""
        self.name = name
        self.device_id = settings.get("device_id")
        self.ip = settings.get("ip")
        self.local_key = settings.get("local_key")
        self.dps = settings.get("dps")  # DPS to control
        self.version = settings.get("version", 3.3)  # Default to 3.3
        self.power = 0

        # Initialize Tuya device
        self.device = tinytuya.Device(self.device_id, self.ip, self.local_key)
        self.device.set_version(self.version)

    def on(self):
        """Turn the device socket on."""
        self.updatePower(100)

    def off(self):
        """Turn the device socket off."""
        self.updatePower(0, force=True)

    def updatePower(self, power, force=False):
        """Update the power state and notify."""
        if power not in [0, 100]:  # Allow only valid power states for Tuya devices
            logger.warning(f"{self.name}: Invalid power value: {power}. Skipping update.")
            return

        try:
            state = power == 100
            if self.power != power or force:  # Prevent redundant state updates
                self.device.set_value(self.dps, state)
                self.power = power
                self.state = "ON" if state else "OFF"
                logger.info(f"{self.name} set to {'ON' if state else 'OFF'}")
            else:
                logger.debug(f"{self.name}: Power state already set to {power}, skipping redundant update.")

            # Notify even if state didn't change, for consistency
            notify(Event(source=self.name, endpoint="power", data=int(self.power)))
        except Exception as e:
            logger.error(f"Error setting power for {self.name}: {e}")

    def getPower(self):
        """Return the current power state."""
        return self.power

    def callback(self, endpoint, data):
        """Handle state updates from the controller."""
        if endpoint == "state":
            if data == 0:
                self.off()
            elif data == 1:
                self.on()
            else:
                logger.warning(f"{self.name}: unsupported data value: {data}")

