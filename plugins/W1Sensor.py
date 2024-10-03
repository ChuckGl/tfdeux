# W1Sensor.py
# 
# Changelog:
#  08-FEB-24: Update to fixes from michaelcadilhac's fork and changed return value to Fahrenheit
#
# Ver: 1.0

import logging
import aiofiles
import asyncio
import datetime
import re
from interfaces import Sensor
from event import notify, Event

logger = logging.getLogger(__name__)

def factory(name, settings):
    id = settings['id']
    offset = settings.get('offset', 0.0)
    pollInterval = settings.get('pollInterval', 2.0)
    sendtime = settings.get('sendtime', 10)
    return W1Sensor(name, id, offset, pollInterval, sendtime)

class W1Sensor(Sensor):
    def __init__(self, name, sensorId, offset=0, pollInterval=0, sendtime=10):
        self.name = name
        self.sensorId = sensorId
        self.offset = offset
        self.lastTemp = 0.0
        self.pollInterval = pollInterval
        self.sendtime = sendtime
        self.last_sendtime = datetime.datetime.min
        asyncio.get_event_loop().create_task(self.run())


    async def run(self):
        while True:
            try:
                self.lastTemp = await self.readTemp() + self.offset
                current_time = datetime.datetime.now()
                if (current_time - self.last_sendtime).total_seconds() >= self.sendtime:
                    notify(Event(source=self.name, endpoint='temperature', data=self.lastTemp))
                    self.last_sendtime = current_time
            except RuntimeError as e:
                logger.debug(str(e))
            await asyncio.sleep(self.pollInterval)

    async def readTemp(self):
        async with aiofiles.open('/sys/bus/w1/devices/%s/w1_slave'% self.sensorId, mode='r') as sensor_file:
            contents = await sensor_file.read()
        match = re.search('YES\n.*=(.*)$', contents)
        if match is None:
            raise RuntimeError("Failed to read W1 Temperature: %s"%contents)
	# Changed return value to F from original "return float(match.group(1)) / 1000" for C and round to 2 decimal
        return round((((float(match.group(1)) / 1000) * 9) / 5) + 32, 2)

    def temp(self):
        return self.lastTemp
