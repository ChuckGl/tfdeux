# filename: DummySensor.py

import asyncio
import os
import logging
from random import normalvariate
from decimal import Decimal
from event import notify, Event
from interfaces import Sensor

logger = logging.getLogger(__name__)

def factory(name, settings):
    return DummySensor(name, settings)

class DummySensor(Sensor):
    def __init__(self, name, settings):
        self.name = name
        self.sensor_type = settings.get('type', 'thermo')
        self.mode = settings.get('mode', 'fixed')
        self.sendtime = int(settings.get('sendtime', 10))
        self.loopTrace = str(settings.get('loopTrace', False)).lower() == 'true'

        self.fakeTemp = float(settings.get('fakeTemp', 68.0))
        self.fakeGravity = float(settings.get('fakeGravity', 1.024))
        self.original_gravity = float(settings.get('startgrav', self.fakeGravity))
        self.temp_offset = float(settings.get('tempclbr', 0.0))
        self.gravity_offset = float(settings.get('gravclbr', 0.0))

        self.traceFile = settings.get('traceFile')
        self.gravityFile = settings.get('gravityFile')

        self.tempTrace = []
        self.gravityTrace = []
        self.tempIndex = 0
        self.gravityIndex = 0

        self.lastTemp = self.fakeTemp
        self.lastGravity = self.fakeGravity

        asyncio.get_event_loop().create_task(self.run())

    def temp(self):
        return self.lastTemp

    def gravity(self):
        return self.lastGravity

    def abv(self):
        try:
            og = self.original_gravity
            fg = self.lastGravity
            abv = (og - fg) * 131.25
            return round(abv, 2)
        except Exception:
            return 0.0

    def atten(self):
        try:
            og = self.original_gravity
            fg = self.lastGravity
            if og > 1.0:
                atten = 100 * ((og - fg) / (og - 1.0))
                return round(atten, 2)
        except Exception:
            return 0.0

    def ograv(self):
        return self.original_gravity

    def brix(self):
        sg = self.lastGravity
        try:
            sg = Decimal(sg)
            brix = (((Decimal('182.4601') * sg - Decimal('775.6821')) * sg + Decimal('1262.7794')) * sg - Decimal('669.5622'))
            return float(brix.quantize(Decimal('0.01')))
        except Exception:
            return 0.0

    def tcalb(self, tempCalb=None):
        if tempCalb is not None:
            self.temp_offset = float(tempCalb)
        return self.temp_offset

    def gcalb(self, gravCalb=None):
        if gravCalb is not None:
            self.gravity_offset = float(gravCalb)
        return self.gravity_offset


    def callback(self, endpoint, data):
        if endpoint == 'temperature' and self.sensor_type in ['thermo', 'tilt']:
            self.fakeTemp = float(data)
        elif endpoint == 'gravity' and self.sensor_type in ['hydro', 'tilt']:
            self.fakeGravity = float(data)
        else:
            super().callback(endpoint, data)

    async def run(self):
        def safe_float(val):
            try:
                return float(val.strip())
            except ValueError:
                return None
        # Load trace files at startup
        if self.mode == 'file' and self.traceFile:
            if os.path.exists(self.traceFile):
                with open(self.traceFile) as f:
                    self.tempTrace = [safe_float(line) for line in f if line.strip()]
        if self.mode == 'file' and self.gravityFile:
            if os.path.exists(self.gravityFile):
                with open(self.gravityFile) as f:
                    self.gravityTrace = [safe_float(line) for line in f if line.strip()]

        while True:
            logger.debug(f"[{self.name}] TempIndex: {self.tempIndex}, GravityIndex: {self.gravityIndex}")
            if self.sensor_type in ['thermo', 'tilt']:
                self.lastTemp = await self.readTemp()
                notify(Event(source=self.name, endpoint='temperature', data=self.lastTemp))

            if self.sensor_type in ['hydro', 'tilt']:
                self.lastGravity = await self.readGravity()
                notify(Event(source=self.name, endpoint='gravity', data=self.lastGravity))
                notify(Event(source=self.name, endpoint='abv', data=self.abv()))
                notify(Event(source=self.name, endpoint='atten', data=self.atten()))
                notify(Event(source=self.name, endpoint='ograv', data=self.ograv()))
                notify(Event(source=self.name, endpoint='brix', data=self.brix()))

            await asyncio.sleep(self.sendtime)

    async def readTemp(self):
        await asyncio.sleep(0.1)
        if self.mode == 'fixed':
            return self.fakeTemp
        elif self.mode == 'random':
            return round(normalvariate(self.fakeTemp, 2.5), 1)
        elif self.mode == 'file' and self.tempTrace:
            if self.tempIndex < len(self.tempTrace):
                value = self.tempTrace[self.tempIndex]
            else:
                value = self.tempTrace[-1] if self.loopTrace else self.fakeTemp

            # Advance index
            self.tempIndex += 1
            if self.loopTrace and self.tempIndex >= len(self.tempTrace):
                self.tempIndex = 0
                logging.warning(f"[{self.name}] Temp trace looped to beginning.")

            if value is None:
                return None
            return round(value, 3)
        return self.fakeTemp

    async def readGravity(self):
        await asyncio.sleep(0.1)
        if self.mode == 'fixed':
            return self.fakeGravity
        elif self.mode == 'random':
            return round(normalvariate(self.fakeGravity, 0.002), 4)
        elif self.mode == 'file' and self.gravityTrace:
            if self.gravityIndex < len(self.gravityTrace):
                value = self.gravityTrace[self.gravityIndex]
            else:
                value = self.gravityTrace[-1] if self.loopTrace else self.fakeGravity

            # Advance index
            self.gravityIndex += 1
            if self.loopTrace and self.gravityIndex >= len(self.gravityTrace):
                self.gravityIndex = 0
                logging.warning(f"[{self.name}] Gravity trace looped to beginning.")

            if value is None:
                return None
            return round(value, 4)
        return self.fakeGravity

