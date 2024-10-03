import asyncio
from random import normalvariate

from interfaces import Sensor
from event import notify, Event

def factory(name, settings):
    sensor_type = settings.get('type')

    # Set default values based on the sensor type
    if sensor_type == 'thermo':
        fakeTemp = settings.get('fakeTemp', 68.5)
        fakeGravity = None  # Not used for thermo
    elif sensor_type == 'hydro':
        fakeTemp = None  # Not used for hydro
        fakeGravity = settings.get('fakeGravity', 1.024)
    elif sensor_type == 'tilt':
        fakeTemp = settings.get('fakeTemp', 68.5)
        fakeGravity = settings.get('fakeGravity', 1.024)
    else:
        raise ValueError(f"Unknown sensor type: {sensor_type}")

    return DummySensor(name, fakeTemp, fakeGravity, sensor_type)

class DummySensor(Sensor):
    def __init__(self, name, fakeTemp, fakeGravity, sensor_type):
        self.fakeTemp = fakeTemp
        self.fakeGravity = fakeGravity
        self.sensor_type = sensor_type
        self.lastTemp = 0
        self.lastGravity = 0
        self.name = name
        asyncio.get_event_loop().create_task(self.run())

    async def run(self):
        while True:
            if self.sensor_type in ['thermo', 'tilt']:
                self.lastTemp = await self.readTemp()
            if self.sensor_type in ['hydro', 'tilt']:
                self.lastGravity = await self.readGravity()
            await asyncio.sleep(10)

    async def readTemp(self):
        if self.fakeTemp is None:
            return None
        await asyncio.sleep(2)
        temp = round(normalvariate(self.fakeTemp, 2.5), 1)
        notify(Event(source=self.name, endpoint='temperature', data=temp))
        return temp

    async def readGravity(self):
        if self.fakeGravity is None:
            return None
        await asyncio.sleep(2)
        gravity = round(normalvariate(self.fakeGravity, 0.01), 3)
        notify(Event(source=self.name, endpoint='gravity', data=gravity))
        return gravity

    def temp(self):
        return self.lastTemp

    def gravity(self):
        return self.lastGravity

    def callback(self, endpoint, data):
        if endpoint == 'temperature' and self.sensor_type in ['thermo', 'tilt']:
            self.fakeTemp = float(data)
        elif endpoint == 'gravity' and self.sensor_type in ['hydro', 'tilt']:
            self.fakeGravity = float(data)
        else:
            super().callback(endpoint, data)

