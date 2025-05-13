# filename: DualLoopLogic.py

import math
import logging

logger = logging.getLogger(__name__)

def factory(name, settings):
    return DualLoopLogic(name, settings)

class DualLoopLogic:
    def __init__(self, name, settings):
        self.outerSensor = settings.get("outerSensor")  # Typically Tilt
        self.innerSensor = settings.get("innerSensor")  # Typically Onewire
        self.innerMinTemp = float(settings.get("innerMinTemp", 28.0))
        self.innerMaxTemp = float(settings.get("innerMaxTemp", 80.0))
        self.baseScale = float(settings.get("baseScale", 0.5))
        self.gain = float(settings.get("gain", 0.3))
        self.hysteresis = float(settings.get("hysteresis", 0.3))
        self.keepCold = settings.get("keepCold", False)
        self.keepHot = settings.get("keepHot", False)
        self.lastOutput = 0.0

    def calc(self, inputs, setpoint):
        target = None
        try:
            beerTemp = float(inputs.get(self.outerSensor))
            airTemp = float(inputs.get(self.innerSensor))
    
            if beerTemp is None or airTemp is None:
                logger.warning("Missing input for beerTemp or airTemp.")
                return self.lastOutput
    
            error = beerTemp - setpoint  # positive = too hot, negative = too cold
            scale = self.baseScale + abs(error) * self.gain
            adjust = abs(error) ** 1.5 * scale
    
            if self.keepCold:
                # Cooling: want air colder if beer is too hot
                if beerTemp < setpoint:
                    # Beer already cooler than setpoint → don't cooler
                    self.lastOutput = 0.0
                else:
                    target = self._clamp(setpoint - adjust, self.innerMinTemp, self.innerMaxTemp)
                    if airTemp > target + self.hysteresis:
                        self.lastOutput = 100.0
                    elif airTemp < target - self.hysteresis:
                        self.lastOutput = 0.0
    
            elif self.keepHot:
                # Heating: want air warmer if beer is too cold
                if beerTemp > setpoint:
                    # Beer already hotter than setpoint → don't heat
                    self.lastOutput = 0.0
                else:
                    target = self._clamp(setpoint + adjust, self.innerMinTemp, self.innerMaxTemp)
                    if airTemp < target - self.hysteresis:
                        self.lastOutput = 100.0
                    elif airTemp > target + self.hysteresis:
                        self.lastOutput = 0.0
            if target is not None:
                logger.warning(f"DualLoopLogic: beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, setpoint={setpoint:.2f}, target={target:.2f}, output={self.lastOutput}")
            else:
                logger.warning(f"DualLoopLogic: beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, setpoint={setpoint:.2f}, target=None, output={self.lastOutput}")
                
            return self.lastOutput
    
        except Exception as e:
            logger.error(f"DualLoopLogic exception: {e}")
            return self.lastOutput

    def _clamp(self, value, min_val, max_val):
        return max(min(value, max_val), min_val)

