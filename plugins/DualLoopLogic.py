# filename: DualLoopLogic.py

import math
import logging
import time
from datetime import datetime


logger = logging.getLogger(__name__)

def factory(name, settings):
    return DualLoopLogic(name, settings)

class DualLoopLogic:
    def __init__(self, name, settings):
        self.name = name
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
        self.coolingLastChanged = None
        self.coolingMinCycleSecs = 300

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
    
            now = time.time()  # Current time for cooldown tracking
    
            if self.keepCold:
                # Cooling logic
                if beerTemp < setpoint:
                    desiredOutput = 0.0
                else:
                    target = self._clamp(setpoint - adjust, self.innerMinTemp, self.innerMaxTemp)
                    if airTemp > target + self.hysteresis:
                        desiredOutput = 100.0
                    elif airTemp < target - self.hysteresis:
                        desiredOutput = 0.0
                    else:
                        desiredOutput = self.lastOutput  # No change
    
                if desiredOutput != self.lastOutput:
                    # Change requested — apply cooldown filter
                    if self.coolingLastChanged is None or (now - self.coolingLastChanged) >= self.coolingMinCycleSecs:
                        self.lastOutput = desiredOutput
                        self.coolingLastChanged = now
                        logger.info(f"Cooling state changed to {self.lastOutput} at {datetime.now().strftime('%H:%M:%S')}")
                    else:
                        time_since = now - self.coolingLastChanged
                        time_remaining = max(0, self.coolingMinCycleSecs - time_since)
                        
                        def fmt(seconds):
                            mins = int(seconds // 60)
                            secs = int(seconds % 60)
                            return f"{mins}m {secs}s"
                        
                        logger.info(
                            f"Cooling change BLOCKED (min cycle delay): "
                            f"last={self.lastOutput}, desired={desiredOutput}, "
                            f"time since change={fmt(time_since)}, time to release={fmt(time_remaining)}"
                        )
                        # Keep previous output (do not apply change)
                # else: desired == current → no action needed
    
            elif self.keepHot:
                # Heating logic (no cooldown needed)
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
                logger.debug(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: DualLoopLogic: controller={self.name}, beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, setpoint={setpoint:.2f}, target={target:.2f}, output={self.lastOutput}")
            else:
                logger.debug(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: DualLoopLogic: controller={self.name}, beerTemp={beerTemp:.2f}, airTemp={airTemp:.2f}, setpoint={setpoint:.2f}, target=None, output={self.lastOutput}")
            return self.lastOutput
    
        except Exception as e:
            logger.error(f"DualLoopLogic exception: {e}")
            return self.lastOutput

    def _clamp(self, value, min_val, max_val):
        return max(min(value, max_val), min_val)

