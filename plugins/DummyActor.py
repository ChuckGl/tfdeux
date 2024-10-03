import logging

from interfaces import Actor
from event import notify, Event

logger = logging.getLogger(__name__)

def factory(name, settings):
    return DummyActor(name)

class DummyActor(Actor):
    def __init__(self, name):
        self.name = name
        self.power = 0

    def on(self):
        self.updatePower(100)
    def off(self):
        self.updatePower(0)

    def updatePower(self, power):
        self.power = power
        if self.power == 0:
            self.state = 'OFF'
        else:
            self.state = 'ON'
        notify(Event(source=self.name, endpoint='power', data=int(self.power)))
        logger.debug("Setting power to %d   %s: ** %s **"%(self.power, self.name.upper(), self.state))

    def getPower(self):
        return self.power

    def callback(self, endpoint, data):
        if endpoint == 'state':
            if data == 0:
                logger.info("Turning %s off"%self.name)
                self.off()
            elif data == 1:
                logger.info("Turning %s on"%self.name)
                self.on()
            else:
                logger.warning("DummyActor:%s unsupported data value: %d"%(self.name, data))
