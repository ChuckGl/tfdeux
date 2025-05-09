# plugins/GembirdActor.py

import logging
import sispm
import time
from syscontroller import usbreset

log = logging.getLogger("GembirdActor")
GEMBIRD_DEVICES = []
LAST_CONNECT_TIME = 0
CONNECT_COOLDOWN = 5  # seconds

def get_device(index):
    global GEMBIRD_DEVICES, LAST_CONNECT_TIME
    now = time.time()
    if now - LAST_CONNECT_TIME < CONNECT_COOLDOWN:
        log.debug("GembirdActor: Skipping sispm.connect() due to cooldown")
        return GEMBIRD_DEVICES[index] if index < len(GEMBIRD_DEVICES) else None
    try:
        GEMBIRD_DEVICES = sispm.connect()
        LAST_CONNECT_TIME = now
        log.debug(f"GembirdActor: sispm.connect() returned {len(GEMBIRD_DEVICES)} device(s)")
        return GEMBIRD_DEVICES[index] if index < len(GEMBIRD_DEVICES) else None
    except Exception as e:
        log.error(f"GembirdActor: Error connecting to EG-PMS2 devices: {e}")
        GEMBIRD_DEVICES = []
        return None

class GembirdActor:
    def __init__(self, name, settings):
        self.name = name
        self.outlet = settings.get("outlet", 1)
        self.device_index = settings.get("device_index", 0)
        self.poll_interval = settings.get("poll_interval", 30)
        self.power = 0.0
        self.device = get_device(self.device_index)
        self.connected = bool(self.device)
        if self.connected:
            log.info(f"{self.name}: Connected to EG-PMS2 outlet {self.outlet}")
        else:
            log.warning(f"{self.name}: Failed to connect to EG-PMS2 device")

    def setPower(self, power):
        if not self.connected:
            self.reconnectDevice()
            if not self.connected:
                log.warning(f"{self.name}: Cannot set power, not connected")
                return

        desired = power >= 50.0
        for attempt in range(2):  # First try + retry
            try:
                current = sispm.getstatus(self.device, self.outlet)
                if current is None:
                    log.error(f"{self.name}: getstatus() returned None — device likely not responding")
                    raise IOError("getstatus failed")
                if current == desired:
                    log.debug(f"{self.name}: No action needed. Outlet already {'ON' if desired else 'OFF'}")
                    self.power = 100.0 if desired else 0.0
                    return
                if desired:
                    sispm.switchon(self.device, self.outlet)
                else:
                    sispm.switchoff(self.device, self.outlet)
                time.sleep(0.1)
                confirm = sispm.getstatus(self.device, self.outlet)
                if confirm == desired:
                    log.info(f"{self.name}: Outlet {self.outlet} confirmed {'ON' if desired else 'OFF'}")
                    self.power = 100.0 if desired else 0.0
                    return
                else:
                    log.warning(f"{self.name}: Attempted to set power to {desired} but still {confirm}")
            except Exception as e:
                log.warning(f"{self.name}: Exception during setPower: {e}")
                self.connected = False

        # Escalation
        log.warning(f"{self.name}: setPower() failed twice — escalating to reconnect")
        if not self.reconnectDevice():
            log.warning(f"{self.name}: reconnectDevice() failed — escalating to rebootSocket()")
            self.rebootSocket()
            if not self.connected or sispm.getstatus(self.device, self.outlet) != desired:
                log.warning(f"{self.name}: rebootSocket() failed — escalating to usbreset()")
                usbreset("04b4", "fd15")  # default vendor/product ID

    def updatePower(self, power):
        self.setPower(power)

    def on(self):
        self.setPower(100.0)

    def off(self):
        self.setPower(0.0)

    def getPower(self):
        return self.power

    def isPowered(self):
        return self.power >= 50.0

    def isReady(self):
        return self.connected

    def pollState(self):
        if not self.connected:
            self.reconnectDevice()
            return
        try:
            state = sispm.getstatus(self.device, self.outlet)
            if state is None:
                log.error(f"{self.name}: getstatus() returned None — device likely not responding")
                self.reconnectDevice()
                return
            actual_power = 100.0 if state else 0.0
            if actual_power != self.power:
                log.info(f"{self.name}: Detected power mismatch: {self.power} → {actual_power}")
                self.setPower(actual_power)
            else:
                log.debug(f"{self.name}: Poll OK. Outlet state matches: {actual_power}")
        except Exception as e:
            log.warning(f"{self.name}: Poll failed with I/O error: {e}")
            self.connected = False

    def rebootSocket(self, delay=2.0):
        log.info(f"{self.name}: Rebooting outlet {self.outlet}")
        try:
            sispm.switchoff(self.device, self.outlet)
            time.sleep(delay)
            sispm.switchon(self.device, self.outlet)
            time.sleep(0.1)
        except Exception as e:
            log.warning(f"{self.name}: Error in rebootSocket: {e}")
            self.connected = False

    def reconnectDevice(self):
        log.info(f"{self.name}: Attempting reconnectDevice()")
        self.device = get_device(self.device_index)
        self.connected = bool(self.device)
        if self.connected:
            log.info(f"{self.name}: Reconnected successfully")
        else:
            log.warning(f"{self.name}: Reconnect failed")
        return self.connected

    def cleanup(self):
        pass

def factory(name, settings):
    return GembirdActor(name, settings)

