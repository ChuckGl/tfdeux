# filename: TPLinkActor.py

import asyncio
import logging
from interfaces import Actor
from event import notify, Event

logger = logging.getLogger(__name__)

def factory(name, settings):
    """Factory function to create a TPLinkActor instance."""
    return TPLinkActor(name, settings)

# Encryption and Decryption of TP-Link Smart Home Protocol
# XOR Autokey Cipher with starting key = 171
def encrypt(string):
    """Encrypts a string using XOR Autokey Cipher with a starting key of 171."""
    key = 171
    result = b"\0\0\0" + chr(len(string)).encode('latin-1')
    for i in string.encode('latin-1'):
        a = key ^ i
        key = a
        result += chr(a).encode('latin-1')
    return result

def decrypt(string):
    """Decrypts a string using XOR Autokey Cipher with a starting key of 171."""
    key = 171
    result = ""
    for i in string:
        a = key ^ i
        key = i
        result += chr(a)
    return result

class TPLinkProtocol(asyncio.Protocol):
    """Protocol class to handle communication with the TP-Link SmartPlug."""
    
    def __init__(self):
        self.transport = None
        self.response_future = None

    def connection_made(self, transport):
        """Handles connection establishment to the SmartPlug."""
        self.transport = transport
        logger.debug("Connected to TPLink SmartPlug")

    def connection_lost(self, exc):
        """Handles connection loss and logs any exceptions."""
        if exc:
            logger.error(f"Connection lost: {exc}")
        if self.response_future and not self.response_future.done():
            self.response_future.set_exception(exc or Exception("Connection lost"))

    def data_received(self, data):
        """Handles data received from the SmartPlug and decrypts it."""
        msg = decrypt(data[4:])
        if self.response_future:
            self.response_future.set_result(msg)
        else:
            logger.info(f"Received data but response_future is in an invalid state")

class TPLinkActor(Actor):
    """Actor class to control a TP-Link SmartPlug."""
    
    onMsg = '{"system":{"set_relay_state":{"state":1}}}'
    offMsg = '{"system":{"set_relay_state":{"state":0}}}'
    infoMsg = '{"system":{"get_sysinfo":{}}}'
    refreshInterval = 10

    def __init__(self, name, settings):
        """Initializes the TPLinkActor with the given name and settings."""
        self.name = name
        self.power = 0
        self.lastPowerState = None
        self.loop = asyncio.get_event_loop()
        self.settings = settings
        asyncio.ensure_future(self.schedule())

    async def schedule(self):
        """Schedules sending on/off messages to the SmartPlug based on power level."""
        while True:
            if self.power == 100.0:
                if self.lastPowerState != 100.0:
                    logger.info(f"{self.name} SmartPlug is now ON")
                await self.send(self.onMsg)
                self.lastPowerState = 100.0
                await asyncio.sleep(self.refreshInterval)
            elif self.power == 0.0:
                if self.lastPowerState != 0.0:
                    logger.info(f"{self.name} SmartPlug is now OFF")
                await self.send(self.offMsg)
                self.lastPowerState = 0.0
                await asyncio.sleep(self.refreshInterval)
            else:
                onTime = self.refreshInterval * self.power / 100.0
                offTime = self.refreshInterval - onTime
                await self.send(self.onMsg)
                await asyncio.sleep(onTime)
                await self.send(self.offMsg)
                await asyncio.sleep(offTime)

    def updatePower(self, power):
        """Updates the power level and sends a notification."""
        self.power = power
        notify(Event(source=self.name, endpoint='power', data=power))

    def getPower(self):
        """Returns the current power level."""
        return self.power

    async def isRelayOn(self):
        """Checks the current state of the SmartPlug and logs whether it is ON or OFF."""
        try:
            # Send the info message to get the relay state
            response = await self.send(self.infoMsg)
            if response:
                # Parse the response to check the relay_state
                if '"relay_state":1' in response:
                    logger.info(f"{self.name} SmartPlug verified ON")
                elif '"relay_state":0' in response:
                    logger.info(f"{self.name} SmartPlug verified OFF")
                else:
                    logger.info(f"Unexpected response from {self.name}: {response}")
            else:
                logger.warning(f"Failed to get response from {self.name}: response: {response}")
        except OSError as e:
            logger.warning(f"TPLinkActor {self.name}: {e}")
            print(f"TPLinkActor {self.name}: {e}")

    async def send(self, msg):
        """Sends an encrypted message to the SmartPlug."""
        try:
            transport, protocol = await self.loop.create_connection(lambda: TPLinkProtocol(), self.settings['ip'], 9999)
            # protocol.response_future = self.loop.create_future() # Uncomment to process responses
            transport.write(encrypt(msg))
            # response = await protocol.response_future # Uncomment to process responses
            # return response # Uncomment to process responses
        except OSError as e:
            logger.warning(f"TPLinkActor {self.name}: {e}")
            return None
        finally:
            transport.close()

    def on(self):
        """Turns the SmartPlug on."""
        logger.info(f"{self.name} SmartPlug is now ON")
        asyncio.ensure_future(self.send(self.onMsg))
        self.updatePower(100.0)

    def off(self):
        """Turns the SmartPlug off."""
        logger.info(f"{self.name} SmartPlug is now OFF")
        asyncio.ensure_future(self.send(self.offMsg))
        self.updatePower(0.0)

    def callback(self, endpoint, data):
        """Handles callbacks for state and power updates."""
        if endpoint == 'state':
            if data == 0:
                self.off()
            elif data == 1:
                self.on()
            else:
                logger.warning(f"TPLinkActor {self.name}: unsupported data value for state endpoint: {data}")
        elif endpoint == 'power':
            if data == 100.0:
                self.on()
            elif data == 0.0:
                self.off()
            else:
                self.updatePower(data)
        else:
            logger.warning(f"TPLinkActor {self.name}: unsupported endpoint {endpoint}")

if __name__ == '__main__':
    def blip():
        """Schedules a repeating task to keep the event loop running."""
        asyncio.get_event_loop().call_later(0.1, blip)

    loop = asyncio.get_event_loop()
    settings = {'ip': '192.168.8.116'}
    actor = factory("TPLinkActor", settings)
    loop.call_soon(blip)

    actor.updatePower(15.0)
    # actor.off()

    try:
        loop.run_forever()
    finally:
        loop.close()

