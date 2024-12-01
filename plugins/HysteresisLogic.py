# filename: HysteresisLogic.py

import event
import interfaces
from event import notify, Event


def factory(name, settings):
    hysteresisOver = settings.get('allowedOvershoot', 0.5)
    hysteresisUnder = settings.get('allowedUndershoot', 0.5)
    keepHot = not settings.get('keepCold', True)
    keepHot = settings.get('keepHot', keepHot)
    event.notify(event.Event(source=name, endpoint='allowedUndershoot', data=hysteresisUnder))
    event.notify(event.Event(source=name, endpoint='allowedOvershoot', data=hysteresisOver))
    if keepHot:
        print ("Keeping %s hot"%name)
        return HysteresisHeatingLogic(hysteresisOver, hysteresisUnder)
    else:
        print ("Keeping %s cold"%name)
        return HysteresisCoolingLogic(hysteresisOver, hysteresisUnder)


class HysteresisCoolingLogic(interfaces.Logic):
    def __init__(self, hysteresisUnder=0.5, hysteresisOver=0.5):
        self.hysteresisUnder = round(hysteresisUnder, 1)
        self.hysteresisOver = round(hysteresisOver, 1)
        self.lastOutput = 0
        self.output = 0

    def shouldAct(self, currentTemp, threshold):
        if self.lastOutput == 1:
            threshold = threshold - self.hysteresisUnder
        else:
            threshold = threshold + self.hysteresisOver

        # print ("CurrentTemp: %f; checking if >= %f for Cooling"%(currentTemp, threshold))
        if currentTemp >= threshold:
            return 1
        else:
            return 0

    def calc(self, input, setpoint):
        self.output = self.shouldAct(input, setpoint)
        self.lastOutput = self.output
        return self.output*100.0

    def callback(self, endpoint, data):
        if endpoint == 'undershoot':
            self.hysteresisUnder = round(float(data), 1)
        elif endpoint == 'overshoot':
            self.hysteresisOver =  round(float(data), 1)
        else:
            super.callback(endpoint, data)

class HysteresisHeatingLogic(HysteresisCoolingLogic):
    def shouldAct(self, currentTemp, threshold):
        if self.lastOutput == 1:
            threshold = threshold + self.hysteresisOver
        else:
            threshold = threshold - self.hysteresisUnder

        # print ("CurrentTemp: %f; checking if <= %f for Heating"%(currentTemp, threshold))
        if currentTemp <= threshold:
            return 1
        else:
            return 0
