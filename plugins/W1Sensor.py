# filename: W1Sensor.py

import aiofiles
import asyncio
import datetime
import logging
import re

from event import notify, Event
from interfaces import Sensor
from plugins.DummySensor import factory as dsfactory

logger = logging.getLogger(__name__)

def factory(name, settings):
    sensor_id = settings['id']
    offset = settings.get('offset', 0.0)
    poll_interval = settings.get('pollInterval', 2.0)
    send_time = settings.get('sendtime', 10)

    # Try to create W1Sensor and validate sensor file availability
    w1sensor = W1Sensor(name, sensor_id, offset, poll_interval, send_time)
    if not w1sensor.is_sensor_available():
        logger.warning(f"Sensor not found. Switching to DummySensor.")
        dsFactory = dsfactory(name, {'type': 'thermo', 'fakeTemp': 60})
        return dsFactory
    return w1sensor

class W1Sensor(Sensor):
    def __init__(self, name, sensor_id, offset=0.0, poll_interval=2.0, send_time=10):
        self.name = name
        self.sensor_id = sensor_id
        self.offset = offset
        self.last_temp = 0.0
        self.poll_interval = poll_interval
        self.send_time = send_time
        self.last_send_time = datetime.datetime.min
        self.running = True
        # Start the polling task
        asyncio.get_event_loop().create_task(self.run())

    def is_sensor_available(self):
        """
        Check if the sensor file exists and is accessible.
        """
        try:
            with open(f'/sys/bus/w1/devices/{self.sensor_id}/w1_slave', mode='r') as sensor_file:
                return True
        except FileNotFoundError:
            return False
        except Exception as e:
            return False

    async def run(self):
        while self.running:
            try:
                self.last_temp = await self.read_temp() + self.offset
                current_time = datetime.datetime.now()
                if (current_time - self.last_send_time).total_seconds() >= self.send_time:
                    notify(Event(source=self.name, endpoint='temperature', data=self.last_temp))
                    self.last_send_time = current_time
            except Exception as e:
                pass
            await asyncio.sleep(self.poll_interval)

    async def read_temp(self):
        try:
            async with aiofiles.open(f'/sys/bus/w1/devices/{self.sensor_id}/w1_slave', mode='r') as sensor_file:
                contents = await sensor_file.read()
            match = re.search('YES\n.*=(.*)$', contents)
            if not match:
                raise RuntimeError(f"Failed to read W1 Temperature: {contents}")
            # Convert to Fahrenheit
            return round((((float(match.group(1)) / 1000) * 9) / 5) + 32, 2)
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error reading W1Sensor file for {self.name}: {e}")
            return None

    def temp(self):
        return self.last_temp

