# filename: DualLoopLogic.py

import logging
from datetime import datetime


logger = logging.getLogger(__name__)


def factory(name, settings):
    return DualLoopLogic(name, settings)


class DualLoopLogic:
    def __init__(self, name, settings):
        self.name = name
        self.outerSensor = settings.get("outerSensor")  # Typically Tilt / BeerSensor
        self.innerSensor = settings.get("innerSensor")  # Typically Onewire / FridgeSensor
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
            beerRaw = inputs.get(self.outerSensor)
            airRaw = inputs.get(self.innerSensor)

            if beerRaw is None or airRaw is None:
                logger.debug("Missing input for beerTemp or airTemp.")
                return self.lastOutput

            beerTemp = float(beerRaw)
            airTemp = float(airRaw)

            error = beerTemp - setpoint  # positive = too hot, negative = too cold
            scale = self.baseScale + abs(error) * self.gain
            adjust = abs(error) ** 1.5 * scale

            if self.keepCold:
                # Cooling logic
                if beerTemp < setpoint:
                    self.lastOutput = 0.0
                else:
                    target = self._clamp(setpoint - adjust, self.innerMinTemp, self.innerMaxTemp)
                    if airTemp > target + self.hysteresis:
                        self.lastOutput = 100.0
                    elif airTemp < target - self.hysteresis:
                        self.lastOutput = 0.0
                    # Else: keep current output

            elif self.keepHot:
                # Heating logic
                if beerTemp > setpoint:
                    self.lastOutput = 0.0
                else:
                    target = self._clamp(setpoint + adjust, self.innerMinTemp, self.innerMaxTemp)
                    if airTemp < target - self.hysteresis:
                        self.lastOutput = 100.0
                    elif airTemp > target + self.hysteresis:
                        self.lastOutput = 0.0
                    # Else: keep current output

            # Log the decision
            if target is not None:
                logger.debug(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: "
                    f"DualLoopLogic: controller={self.name}, "
                    f"beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, "
                    f"setpoint={setpoint:.2f}, target={target:.2f}, output={self.lastOutput}"
                )
            else:
                logger.debug(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: "
                    f"DualLoopLogic: controller={self.name}, "
                    f"beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, "
                    f"setpoint={setpoint:.2f}, target=None, output={self.lastOutput}"
                )

            return self.lastOutput

        except Exception as e:
            logger.error(f"DualLoopLogic exception: {e}")
            return self.lastOutput

    def _clamp(self, value, min_val, max_val):
        return max(min(value, max_val), min_val)
