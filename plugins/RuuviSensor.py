# filename: plugins/RuuviSensor.py

import asyncio
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from event import notify, Event
from plugins.BLEScanner import BLEScanner

logger = logging.getLogger(__name__)


# Factory function to create RuuviSensor instances
def factory(name, settings):
    return RuuviSensor(
        name=name,
        mac=settings['mac'],
        tempcalbr=settings.get('tempclbr', 0.0),
        sendtime=settings.get('sendtime', 30),
    )


# RuuviSensor class handles data processing and notification for a specific RuuviTag
class RuuviSensor:
    def __init__(self, name, mac, tempcalbr, sendtime):
        self.name = name
        self.mac = self._normalize_mac(mac)
        self.temp_offset = Decimal(tempcalbr).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.sendtime = int(sendtime)
        self.last_sendtime = datetime.datetime.min

        # Data freshness tracking
        self.last_value_received = datetime.datetime.now() - self._cache_expiry_seconds()

        # Last known values
        self.lastTemp = Decimal('0.0').quantize(Decimal('0.01'))
        self.lastHumidity = None
        self.lastPressure = None
        self.lastBattery = None
        self.lastMovement = None
        self.lastSequence = None
        self.rssi = 0

        # Register with shared scanner
        scanner = BLEScanner.instance()
        scanner.register(self.process_ble_beacon)
        asyncio.get_event_loop().create_task(scanner.start())

    # Normalize MAC for consistent matching
    def _normalize_mac(self, mac):
        return str(mac).strip().lower().replace('-', ':')

    # Freshness window
    def _cache_expiry_seconds(self):
        return datetime.timedelta(seconds=max(self.sendtime * 4, 120))

    # Is cached data stale?
    def expired(self):
        return self.last_value_received <= datetime.datetime.now() - self._cache_expiry_seconds()

    # Return current temp
    def temp(self):
        return self.lastTemp

    # Return current humidity
    def humidity(self):
        return self.lastHumidity

    # Return current pressure
    def pressure(self):
        return self.lastPressure

    # Return current battery
    def battery(self):
        return self.lastBattery

    # Return current movement counter
    def movement(self):
        return self.lastMovement

    # Return current RSSI
    def signal(self):
        return self.rssi

    # Allow temp calibration updates from backend/UI
    def tcalb(self, tempCalb=None):
        if tempCalb is not None:
            self.temp_offset = Decimal(tempCalb).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return self.temp_offset

    # Parse signed 16-bit big-endian
    @staticmethod
    def _int16(msb, lsb):
        value = (msb << 8) | lsb
        if value & 0x8000:
            value -= 0x10000
        return value

    # Parse unsigned 16-bit big-endian
    @staticmethod
    def _uint16(msb, lsb):
        return (msb << 8) | lsb

    # Convert Celsius to Fahrenheit
    @staticmethod
    def _c_to_f(temp_c):
        return ((temp_c * Decimal('9') / Decimal('5')) + Decimal('32')).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP
        )

    # Extract MAC from RAWv2 payload final 6 bytes
    @staticmethod
    def _payload_mac(payload_bytes):
        return ':'.join(f'{b:02x}' for b in payload_bytes[-6:])

    # Process incoming BLE beacon data
    def process_ble_beacon(self, data):
        import aioblescan as aiobs

        ev = aiobs.HCI_Event()
        try:
            ev.decode(data)
        except Exception as e:
            logger.error(f"RuuviSensor {self.name}: failed to decode BLE event: {e}")
            return False

        if ev.raw_data is None:
            return False

        try:
            manufacturer_data = ev.retrieve("Manufacturer Specific Data")
            if not manufacturer_data:
                return False

            # Walk all manufacturer data entries in case multiple are present
            for entry in manufacturer_data:
                try:
                    payload_bytes = entry.payload[1].val
                except Exception:
                    continue

                if not payload_bytes:
                    continue

                # In your environment the Manufacturer Specific Data payload
                # begins directly with Ruuvi RAWv2 format byte 0x05, not 0x99 0x04 0x05.
                if payload_bytes[0] != 0x05:
                    continue

                # RAWv2 payload should be 24 bytes
                if len(payload_bytes) < 24:
                    continue

                ruuvi_payload = payload_bytes

                adv_mac = self._payload_mac(ruuvi_payload)
                if adv_mac != self.mac:
                    continue

                # RAWv2 field decoding
                # Byte offsets are relative to format byte at index 0
                raw_temp = self._int16(ruuvi_payload[1], ruuvi_payload[2])
                raw_humidity = self._uint16(ruuvi_payload[3], ruuvi_payload[4])
                raw_pressure = self._uint16(ruuvi_payload[5], ruuvi_payload[6])
                raw_power = self._uint16(ruuvi_payload[13], ruuvi_payload[14])
                raw_movement = ruuvi_payload[15]
                raw_sequence = self._uint16(ruuvi_payload[16], ruuvi_payload[17])

                # Temperature: signed 16-bit, 0.005 C units
                if raw_temp == -32768:
                    temperature_c = None
                    temperature_f = None
                else:
                    temperature_c = (Decimal(raw_temp) * Decimal('0.005')) + self.temp_offset
                    temperature_c = temperature_c.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    temperature_f = self._c_to_f(temperature_c)

                # Humidity: unsigned 16-bit, 0.0025 % units; 0xFFFF = invalid
                if raw_humidity == 65535:
                    humidity = None
                else:
                    humidity = (Decimal(raw_humidity) * Decimal('0.0025')).quantize(
                        Decimal('0.01'),
                        rounding=ROUND_HALF_UP
                    )

                # Pressure: unsigned 16-bit + 50000 Pa offset; 0xFFFF = invalid
                if raw_pressure == 65535:
                    pressure = None
                else:
                    pressure = raw_pressure + 50000

                # Power info:
                # first 11 bits = battery mV above 1.6V
                # last 5 bits = tx power above -40 dBm in 2 dBm steps
                if raw_power == 0xFFFF:
                    battery_mv = None
                    tx_power_dbm = None
                else:
                    battery_mv = 1600 + (raw_power >> 5)
                    tx_power_dbm = -40 + ((raw_power & 0x1F) * 2)

                rssi_values = ev.retrieve("rssi")
                rssi = rssi_values[-1].val if rssi_values else 0

                # Store latest values
                self.last_value_received = datetime.datetime.now()
                if temperature_f is not None:
                    self.lastTemp = temperature_f
                self.lastHumidity = humidity
                self.lastPressure = pressure
                self.lastBattery = battery_mv
                self.lastMovement = raw_movement
                self.lastSequence = raw_sequence
                self.rssi = rssi

                # Notify on configured interval
                current_time = datetime.datetime.now()
                if (current_time - self.last_sendtime).total_seconds() >= self.sendtime:
                    if temperature_f is not None:
                        notify(Event(source=self.name, endpoint='temperature', data=float(temperature_f)))
                    # Notify for battery if needed.
                    #if battery_mv is not None:
                    #    notify(Event(source=self.name, endpoint='battery', data=int(battery_mv)))

                    self.last_sendtime = current_time

                return True

        except Exception as e:
            logger.error(f"RuuviSensor {self.name}: error processing BLE beacon: {e}", exc_info=True)
            return False

        return False
