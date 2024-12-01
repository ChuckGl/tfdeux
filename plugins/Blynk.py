# filename: Blynk.py

import asyncio
import BlynkLib
import logging

import interfaces
from event import notify, Event

logger = logging.getLogger(__name__)

def factory(name, settings):
    blynkServer = settings.get('server','blynk.cloud')
    blynkPort = settings.get('port', 443)
    component = BlynkComponent(name, blynkServer, blynkPort, settings['token'])
    return component

class BlynkComponent(interfaces.Component):
    def __init__(self, name, server, port, token):
        self.name = name
        self.server = server
        self.port = port
        self.token = token
        self.blynk = BlynkLib.Blynk(self.token, server=self.server)
        self.loop = asyncio.get_event_loop()
        self.loop.create_task(self.blynk_task())

    def convert_bool(self, value, to_blynk=True):
        if to_blynk:
            # Converting True/False to 1/0 for Blynk
            return 1 if value is True else 0
        else:
            # Converting 1/0 from Blynk to True/False
            return True if int(value) == 1 else False

    async def blynk_task(self):
        @self.blynk.on("V*")
        def blynk_handle_vpins(pin, value):
            pin = int(pin)
            data=round(float(value[0]))
            if 17 <= pin <= 20:
                # Convert 1/0 from Blynk to True/False
                converted_value = self.convert_bool(int(value[0]), to_blynk=False)
                notify(Event(source=self.name, endpoint='v%d'% pin, data=converted_value))
            else:
                notify(Event(source=self.name, endpoint='v%d'% pin, data=round(float(value[0]), 1)))

        @self.blynk.on("connected")
        def blynk_connected(ping):
            print("Access granted, happy Blynking!")
            print('Blynk ready. Ping:', ping, 'ms')

        while True:
            self.blynk.run()
            await asyncio.sleep(0.1)  # Adjust sleep time as needed

    def callback(self, endpoint, data):
        pin = int(endpoint[1:])
        if 17 <= pin <= 20:
            # Convert True/False to 1/0 before sending to Blynk
            converted_data = self.convert_bool(data, to_blynk=True)
            self.blynk.virtual_write(pin, converted_data)
        else:
            self.blynk.virtual_write(pin, data)
