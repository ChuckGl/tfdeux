# filename: InkbirdSensor.py

import asyncio
import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP

from event import notify, Event
from plugins.BLEScanner import BLEScanner

logger = logging.getLogger(__name__)

# Factory function
def factory(name, settings):
    return InkbirdSensor(
        name=name,
        mac=settings["mac"],
        sendtime=settings.get("sendtime", 10),
        tempcalbr=settings.get("tempclbr", 0.0),
    )

# ---------- BLE Parsing Helpers ----------

def _mac_to_str(addr6_le: bytes) -> str:
    b = addr6_le[::-1]
    return ":".join(f"{x:02x}" for x in b).lower()

def _parse_ad_structures(payload: bytes):
    i = 0
    while i < len(payload):
        l = payload[i]
        if l == 0:
            break
        if i + 1 >= len(payload):
            break
        ad_type = payload[i + 1]
        ad_data = payload[i + 2 : i + 1 + l]
        yield ad_type, ad_data
        i += 1 + l

def _parse_le_advertising_reports(pkt: bytes):
    if len(pkt) < 4 or pkt[0] != 0x04:
        return []

    if pkt[1] != 0x3E:
        return []

    plen = pkt[2]
    params = pkt[3 : 3 + plen]
    if len(params) < 2 or params[0] != 0x02:
        return []

    num = params[1]
    off = 2
    out = []

    for _ in range(num):
        if off + 9 > len(params):
            break

        # event_type = params[off + 0]
        # addr_type  = params[off + 1]
        addr = params[off + 2 : off + 8]
        data_len = params[off + 8]
        off += 9

        if off + data_len + 1 > len(params):
            break

        data = params[off : off + data_len]
        rssi = int.from_bytes(
            params[off + data_len : off + data_len + 1],
            "little",
            signed=True,
        )
        off += data_len + 1

        out.append((addr, data, rssi))

    return out

def _decode_temp_c_from_msd(msd: bytes):
    if len(msd) < 2:
        return None
    raw = int.from_bytes(msd[0:2], byteorder="little", signed=True)
    return Decimal(raw) / Decimal(100)

def _c_to_f(temp_c: Decimal) -> Decimal:
    return (temp_c * Decimal(9) / Decimal(5) + Decimal(32)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

def _parse_name_from_ad(ad_payload: bytes):
    for ad_type, ad_data in _parse_ad_structures(ad_payload):
        # 0x08 = Shortened Local Name, 0x09 = Complete Local Name
        if ad_type in (0x08, 0x09):
            try:
                return ad_data.decode("utf-8", errors="ignore").strip().lower()
            except Exception:
                return None
    return None

def _parse_msd_from_ad(ad_payload: bytes):
    for ad_type, ad_data in _parse_ad_structures(ad_payload):
        if ad_type == 0xFF:
            return ad_data
    return None

# ---------- Inkbird Sensor ----------

class InkbirdSensor:
    def __init__(self, name, mac, sendtime, tempcalbr):
        self.name = name
        self.mac = mac.lower()
        self.sendtime = int(sendtime)

        # Calibration in °F
        self.temp_offset = Decimal(str(tempcalbr)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        self.lastTemp = Decimal("0.0").quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        self.last_value_received = (
            datetime.datetime.now() - datetime.timedelta(days=1)
        )
        self.last_sendtime = datetime.datetime.min
        self.rssi = 0

        scanner = BLEScanner.instance()
        scanner.register(self.process_ble_packet)
        asyncio.get_event_loop().create_task(scanner.start())

    # ---------- Public API ----------

    def temp(self):
        return self.lastTemp

    def tcalb(self, tempCalb=None):
        if tempCalb is not None:
            self.temp_offset = Decimal(str(tempCalb)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        return self.temp_offset

    def expired(self) -> bool:
        return self.last_value_received <= (
            datetime.datetime.now() - datetime.timedelta(seconds=120)
        )

    # ---------- BLE Packet Processing ----------

    def process_ble_packet(self, pkt: bytes):
        reports = _parse_le_advertising_reports(pkt)
        if not reports:
            return False

        for addr_le, ad_payload, rssi in reports:
            mac = _mac_to_str(addr_le)
            if mac != self.mac:
                continue

            local_name = _parse_name_from_ad(ad_payload)
            msd = _parse_msd_from_ad(ad_payload)

            if msd is None:
                continue

            # Reject Apple iBeacon / Tilt packets.
            # Tilt uses Apple company ID 0x004C, which appears as 4c 00
            # at the start of the manufacturer-specific payload.
            if len(msd) >= 2 and msd[0:2] == b"\x4c\x00":
                continue

            # Accept only Inkbird-looking packets.
            #
            # Real Inkbird IBS-TH2 devices are commonly seen as local names
            # "sps" and "tps". The simulator should advertise "tps" for the
            # Inkbird frame so the same parser works for both.
            if local_name not in ("sps", "tps"):
                continue

            temp_c = _decode_temp_c_from_msd(msd)
            if temp_c is None:
                continue

            temp_f = _c_to_f(temp_c)

            # Apply calibration offset (in °F)
            temp_f = (temp_f + self.temp_offset).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            self.lastTemp = temp_f
            self.last_value_received = datetime.datetime.now()
            self.rssi = int(rssi)

            now = datetime.datetime.now()
            if (now - self.last_sendtime).total_seconds() >= self.sendtime:
                notify(
                    Event(
                        source=self.name,
                        endpoint="temperature",
                        data=float(temp_f),
                    )
                )
                self.last_sendtime = now

            return True

        return False
