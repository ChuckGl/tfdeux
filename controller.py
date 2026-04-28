# filename: controller.py 08APR2026

import asyncio
import decimal
import json
import logging
import os
import sockjs
import subprocess
import sys
from aiohttp import web
from datetime import datetime
from ruamel.yaml import YAML
from time import time

import event
import interfaces
import syscontroller
from common import app, components


logger = logging.getLogger(__name__)

HISTORY_SIZE = 1440
HISTORY_FILE_PATH = '/home/pi/tfdeux/history'

CONFIG_PATH = '/home/pi/tfdeux/config.yaml'


# Update a sensor setting in config.yaml
def update_config_file(sensor_name, key, value):
    yaml = YAML()
    try:
        with open(CONFIG_PATH, "r") as file:
            config = yaml.load(file)

        for sensor in config["sensors"]:
            if sensor_name in sensor:
                if key in sensor[sensor_name]:
                    sensor[sensor_name][key] = value
                    break
        else:
            raise KeyError(f"Sensor {sensor_name} or key {key} not found in config.yaml")

        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file)

        logger.info(f"Updated config.yaml: {sensor_name} -> {key} = {value}")
    except Exception as e:
        logger.error(f"Failed to update config.yaml: {e}")


# Update a controller setting in config.yaml
def update_controller_config(controller_name, key, value):
    yaml = YAML()
    try:
        with open(CONFIG_PATH, "r") as file:
            config = yaml.load(file)

        for controller_entry in config["controllers"]:
            if controller_name in controller_entry:
                controller_entry[controller_name][key] = value
                break
        else:
            raise KeyError(f"Controller {controller_name} not found in config.yaml")

        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file)

        logger.info(f"Updated config.yaml controller: {controller_name} -> {key} = {value}")
    except Exception as e:
        logger.error(f"Failed to update controller config.yaml: {e}")


class Controller(interfaces.Component, interfaces.Runnable):
    def __init__(
        self,
        name,
        sensor,
        actor,
        logic,
        targetTemp=0.0,
        initiallyEnabled=False,
        initiallyAutomatic=False,
        reload_history='no',
        power_guard=None
    ):
        self.fridge_sensor = components.get('FridgeSensor')
        self.name = name
        self._enabled = initiallyEnabled
        self._autoMode = initiallyAutomatic
        self.sensor = sensor
        self.actor = actor
        self.targetTemp = targetTemp
        self.logic = logic

        self.timestamp_history = []
        self.power_history = []
        self.temp_history = []
        self.setpoint_history = []
        self.fridge_temp_history = []
        self.gravity_history = []
        self.abv_history = []
        self.atten_history = []
        self.ograv_history = []
        self.history_file = os.path.join(HISTORY_FILE_PATH, f'{name}_history.json')

        # Track whether we've already logged an active stale-sensor fault
        self._stale_sensor_fault_active = False

        # UI/status visibility fields
        self._requested_power = 0.0
        self._applied_power = 0.0
        self._guard_state = None
        self._guard_remaining_sec = 0
        self._status_text = "Idle"

        # Power guard settings (compressor protection / long-run rest)
        self.power_guard = power_guard or {}
        now = time()
        min_off_seed = float(self.power_guard.get('minOffSec', 300))
        self._guard_runtime = {
            'current_on': False,
            'last_change': now - min_off_seed,
            'on_start': None,
            'rest_until': 0.0,
            'last_applied_power': None,
            'last_reason': None,
        }

        if reload_history.lower() == 'yes':
            self.load_history()

        sockjs.add_endpoint(
            app,
            prefix=f'/controllers/{self.name}/ws',
            name=f'{self.name}-ws',
            handler=self.websocket_handler
        )
        asyncio.ensure_future(self.run())

        event.notify(event.Event(source=self.name, endpoint='initialSetpoint', data=self.targetTemp))
        event.notify(event.Event(source=self.name, endpoint='enabled', data=self._enabled))
        event.notify(event.Event(source=self.name, endpoint='automatic', data=self._autoMode))

    # Safely determine whether a sensor is stale
    def _sensor_is_stale(self, sensor):
        if sensor is None:
            return False

        expired_method = getattr(sensor, 'expired', None)
        if not callable(expired_method):
            return False

        try:
            return bool(expired_method())
        except Exception as e:
            logger.error(
                f"{self.name}: Failed to check sensor expiry for "
                f"{getattr(sensor, 'name', sensor.__class__.__name__)}: {e}"
            )
            return True

    # Map a free-form guard reason to a UI-friendly state string
    def _reason_to_guard_state(self, reason):
        if reason == "FORCE":
            return "FORCE"
        if reason == "No guard":
            return "NO_GUARD"
        if reason == "Turn ON":
            return "TURN_ON"
        if reason == "Turn OFF":
            return "TURN_OFF"
        if reason.startswith("MinOn block"):
            return "MIN_ON_BLOCK"
        if reason.startswith("MinOff block"):
            return "MIN_OFF_BLOCK"
        if reason.startswith("MaxOn rest"):
            return "MAX_ON_REST"
        if reason.startswith("REST active"):
            return "REST_ACTIVE"
        if reason.startswith("REST override"):
            return "REST_OVERRIDE"
        if reason.startswith("Hold"):
            return "HOLD"
        return "UNKNOWN"

    # Build a human-readable status line for the UI
    def _build_status_text(self):
        if self.name == "System":
            return "System controller"

        requested_on = float(self._requested_power) >= 50.0
        applied_on = float(self._applied_power) >= 50.0
        guard_state = self._guard_state
        remaining = int(self._guard_remaining_sec or 0)

        mode_word = "Automatic" if self._autoMode else "Manual"

        if not self._enabled:
            return "Disabled"

        if self._stale_sensor_fault_active:
            if self._autoMode:
                return f"{mode_word}; sensor stale; forced OFF"
            return f"{mode_word}; sensor stale; output {'ON' if applied_on else 'OFF'}"

        # PowerGuard states first, even in Manual mode
        if guard_state == "MIN_ON_BLOCK":
            return f"{mode_word}; holding ON ({remaining}s remaining)"
        if guard_state == "MIN_OFF_BLOCK":
            return f"{mode_word}; waiting to restart ({remaining}s remaining)"
        if guard_state == "REST_ACTIVE":
            return f"{mode_word}; forced rest ({remaining}s remaining)"
        if guard_state == "MAX_ON_REST":
            return f"{mode_word}; rest started ({remaining}s remaining)"
        if guard_state == "REST_OVERRIDE":
            return f"{mode_word}; rest override; output ON"
        if guard_state == "TURN_ON":
            return f"{mode_word}; output turned ON"
        if guard_state == "TURN_OFF":
            return f"{mode_word}; output turned OFF"

        # Normal behavior
        if requested_on and applied_on:
            return f"{mode_word}; request ON; output ON"
        if (not requested_on) and (not applied_on):
            return f"{mode_word}; request OFF; output OFF"
        if requested_on and (not applied_on):
            return f"{mode_word}; request ON; blocked ({remaining}s remaining)"
        if (not requested_on) and applied_on:
            return f"{mode_word}; request OFF; holding ON ({remaining}s remaining)"

        # Manual fallback
        if not self._autoMode:
            return f"{mode_word}; output {'ON' if applied_on else 'OFF'}"

        return "Idle"

    def callback(self, endpoint, data):
        includeSetpoint = True

        if self.name == "System":
            yaml = YAML()
            try:
                with open(CONFIG_PATH, "r") as file:
                    config = yaml.load(file)

                for controller_entry in config.get("controllers", []):
                    for controller_name, conrtroller_details in controller_entry.items():
                        controller_instance = components.get(controller_name)
                        if controller_instance and hasattr(controller_instance, "automatic"):
                            controller_instance.automatic = False
                            logger.info(f"Set controller {controller_name} to MANUAL mode.")

                for actor_entry in config.get("actors", []):
                    for actor_name, actor_details in actor_entry.items():
                        actor_instance = components.get(actor_name)
                        if actor_instance and hasattr(actor_instance, "off") and callable(actor_instance.off):
                            logger.info(f"Turning off actor: {actor_name} {actor_instance}")
                            actor_instance.off()

                for sensor_entry in config.get("sensors", []):
                    for sensor_name, sensor_details in sensor_entry.items():
                        sensor_instance = components.get(sensor_name)
                        if sensor_instance and hasattr(sensor_instance, "shutdown") and callable(sensor_instance.shutdown):
                            logger.info(f"Shutting down sensor: {sensor_name} {sensor_instance}")
                            asyncio.create_task(sensor_instance.shutdown())
            except Exception as e:
                logger.error(f"Failed to process sensors and actors from config.yaml: {e}")

            syscontroller.handle_system_command(endpoint, data, controller_name=self.name)

        elif endpoint in ['state', 'enabled']:
            self.enabled = bool(data)
            self._set_power_guarded(0.0, source='callback', force=True)
            update_controller_config(self.name, "initialState", "on" if self.enabled else "off")
            state_text = "ENABLED" if bool(data) else "DISABLED"
            logger.info(f"Setting controller {self.name} to {state_text}")

        elif endpoint == 'automatic':
            self.automatic = bool(data)
            update_controller_config(self.name, "automatic", self.automatic)

            # When entering Manual, preserve current actual output as the starting manual request
            if not self._autoMode:
                current_power = float(self.actor.getPower()) if self.actor is not None else 0.0
                self._requested_power = current_power
                self._applied_power = current_power

            self._status_text = self._build_status_text()
            mode_text = "AUTOMATIC" if self._autoMode else "MANUAL"
            logger.info(f"Setting controller {self.name} to {mode_text}")

        elif endpoint == 'setpoint':
            self.setSetpoint(float(data))
            update_controller_config(self.name, "initialSetpoint", float(data))
            includeSetpoint = True

        elif endpoint == 'power':
            applied = self._set_power_guarded(float(data), source='manual', current_temp=self.sensor.temp() if self.sensor else None)
            logger.info(f"Setting {self.name} controller power to {float(data)} (applied {applied})")

        elif endpoint == 'ograv':
            logger.info(f"Setting {self.name} Tilt starting gravity to {data}")
            self.sensor.ograv(float(data))
            update_config_file(self.sensor.name, "startgrav", float(data))

        elif endpoint == 'tcalb':
            logger.info(f"Offsetting {self.name} Tilt temperature by {data}")
            self.sensor.tcalb(float(data))
            update_config_file(self.sensor.name, "tempclbr", float(data))

        elif endpoint == 'gcalb':
            logger.info(f"Offsetting {self.name} Tilt gravity by {data}")
            update_config_file(self.sensor.name, "gravclbr", float(data))
            self.sensor.gcalb(float(data))

        else:
            self.logic.callback(endpoint, data)

    def setSetpoint(self, setpoint):
        self.targetTemp = setpoint
        event.notify(event.Event(source=self.name, endpoint='setpoint', data=self.targetTemp))
        logger.info(f"Setting {self.name} Setpoint to {self.targetTemp}")

    def broadcastDetails(self, includeSetpoint=True):
        manager = sockjs.get_manager(f'{self.name}-ws', app)
        details = self.getDetails()
        if not includeSetpoint:
            details.pop('setpoint', None)
        manager.broadcast(details)

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, state):
        self._enabled = state
        if not self._enabled:
            self._set_power_guarded(0.0, source='callback', force=True)
        event.notify(event.Event(source=self.name, endpoint='enabled', data=self.enabled))

    @property
    def automatic(self):
        return self._autoMode

    @automatic.setter
    def automatic(self, state):
        self._autoMode = state
        event.notify(event.Event(source=self.name, endpoint='automatic', data=self.automatic))

    def getDetails(self):
        if self.name == 'System':
            details = {
                'name': self.name,
                'wsUrl': f'/controllers/{self.name}/ws',
                'requestedPower': self._requested_power,
                'appliedPower': self._applied_power,
                'guardState': self._guard_state,
                'guardRemainingSec': self._guard_remaining_sec,
                'statusText': self._status_text,
            }
        else:
            primary_sensor_stale = self._sensor_is_stale(self.sensor)
            fridge_sensor_stale = self._sensor_is_stale(self.fridge_sensor)

            details = {
                'name': self.name,
                'temperature': None if primary_sensor_stale else self.sensor.temp(),
                'fridgeTemperature': None if fridge_sensor_stale else self.fridge_sensor.temp(),
                'gravity': None if primary_sensor_stale else self.sensor.gravity(),
                'abv': None if primary_sensor_stale else self.sensor.abv(),
                'atten': None if primary_sensor_stale else self.sensor.atten(),
                'ograv': self.sensor.ograv(),
                'tcalb': self.sensor.tcalb(),
                'gcalb': self.sensor.gcalb(),
                'enabled': self.enabled,
                'automatic': self.automatic,
                'power': self.actor.getPower(),
                'setpoint': self.targetTemp,
                'wsUrl': f'/controllers/{self.name}/ws',
                'requestedPower': self._requested_power,
                'appliedPower': self._applied_power,
                'guardState': self._guard_state,
                'guardRemainingSec': self._guard_remaining_sec,
                'statusText': self._status_text,
                'sensorStale': primary_sensor_stale,
                'fridgeSensorStale': fridge_sensor_stale,
            }

        for key, value in details.items():
            if isinstance(value, decimal.Decimal):
                details[key] = float(value)

        return details

    @staticmethod
    def mostredundanttime(ar):
        mint = float('inf')
        minpos = -1
        for i in range(1, len(ar) - 1):
            delta = ar[i + 1] - ar[i - 1]
            if delta < mint:
                mint = delta
                minpos = i
        return minpos

    def save_history(self):
        def convert_decimal(value):
            if isinstance(value, decimal.Decimal):
                return float(value)
            elif isinstance(value, list):
                return [convert_decimal(item) for item in value]
            elif isinstance(value, dict):
                return {key: convert_decimal(val) for key, val in value.items()}
            return value

        data = {
            'timestamp': self.timestamp_history,
            'power': self.power_history,
            'temperature': self.temp_history,
            'setpoint': self.setpoint_history,
            'fridgeTemperature': self.fridge_temp_history,
            'gravity': self.gravity_history,
            'abv': self.abv_history,
            'atten': self.atten_history,
            'ograv': self.ograv_history
        }

        data = convert_decimal(data)

        try:
            with open(self.history_file, 'w') as file:
                json.dump(data, file)
        except Exception as e:
            logger.error(f"Failed to save history for {self.name}: {e}")

    def load_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as file:
                    data = json.load(file)
                self.timestamp_history = data.get('timestamp', [])
                self.power_history = data.get('power', [])
                self.temp_history = data.get('temperature', [])
                self.setpoint_history = data.get('setpoint', [])
                self.fridge_temp_history = data.get('fridgeTemperature', data.get('w1temperature', []))
                self.gravity_history = data.get('gravity', [])
                self.abv_history = data.get('abv', [])
                self.atten_history = data.get('atten', [])
                self.ograv_history = data.get('ograv', [])
        except Exception as e:
            logger.error(f"Failed to load history for {self.name}: {e}")

    # Apply compressor-safe timing and optional long-run rest.
    # This does NOT change the control logic output; it only gates what we actually apply to the actor.
    def _apply_power_guard(self, requested_power, current_temp=None):
        guard = self.power_guard or {}

        min_on = float(guard.get('minOnSec', 180))
        min_off = float(guard.get('minOffSec', 300))
        max_on = guard.get('maxOnSec', None)
        rest_off = float(guard.get('restOffSec', 900))
        rest_skip_delta = guard.get('restSkipDelta', None)

        now = time()
        requested_on = float(requested_power) >= 50.0

        st = self._guard_runtime
        current_on = bool(st.get('current_on', False))
        last_change = float(st.get('last_change', now))
        on_start = st.get('on_start', None)
        rest_until = float(st.get('rest_until', 0.0))

        remaining_sec = 0

        def rest_override_allowed():
            if rest_skip_delta is None:
                return False
            try:
                if current_temp is None:
                    return False
                return float(current_temp) > (float(self.targetTemp) + float(rest_skip_delta))
            except Exception:
                return False

        if rest_until > now:
            remaining_sec = max(0, int(rest_until - now))
            if requested_on and rest_override_allowed():
                st['rest_until'] = 0.0
                rest_until = 0.0
                reason = f"REST override (temp {current_temp} > setpoint {self.targetTemp} + {rest_skip_delta})"
                return 100.0, reason, 0
            else:
                return 0.0, f"REST active until {rest_until:.0f}", remaining_sec

        if requested_on != current_on:
            if requested_on:
                off_time = now - last_change
                if off_time < min_off:
                    remaining_sec = max(0, int(min_off - off_time))
                    return 0.0, f"MinOff block ({off_time:.0f}s < {min_off:.0f}s)", remaining_sec

                st['current_on'] = True
                st['last_change'] = now
                st['on_start'] = now
                return 100.0, "Turn ON", 0

            else:
                if on_start is None:
                    on_start = last_change
                on_time = now - float(on_start)
                if on_time < min_on:
                    remaining_sec = max(0, int(min_on - on_time))
                    return 100.0, f"MinOn block ({on_time:.0f}s < {min_on:.0f}s)", remaining_sec

                st['current_on'] = False
                st['last_change'] = now
                st['on_start'] = None
                return 0.0, "Turn OFF", 0

        if current_on and requested_on and max_on is not None:
            try:
                max_on = float(max_on)
                if on_start is None:
                    on_start = last_change
                    st['on_start'] = on_start
                on_time = now - float(on_start)
                if on_time >= max_on:
                    st['rest_until'] = now + rest_off
                    st['current_on'] = False
                    st['last_change'] = now
                    st['on_start'] = None
                    return 0.0, f"MaxOn rest ({on_time:.0f}s >= {max_on:.0f}s). Resting {rest_off:.0f}s", int(rest_off)
            except Exception:
                pass

        return 100.0 if current_on else 0.0, "Hold", 0

    def _set_power_guarded(self, requested_power, source="auto", force=False, current_temp=None):
        self._requested_power = float(requested_power)

        if force or not (self.power_guard or {}):
            applied = float(requested_power)
            reason = "FORCE" if force else "No guard"
            remaining_sec = 0

            st = self._guard_runtime
            now = time()
            applied_on = float(applied) >= 50.0
            current_on = bool(st.get('current_on', False))

            if applied_on != current_on:
                st['current_on'] = applied_on
                st['last_change'] = now
                st['on_start'] = now if applied_on else None
                st['rest_until'] = 0.0
        else:
            applied, reason, remaining_sec = self._apply_power_guard(requested_power, current_temp=current_temp)

        st = self._guard_runtime
        last_applied = st.get('last_applied_power', None)

        if last_applied is None or float(last_applied) != float(applied):
            try:
                self.actor.updatePower(applied)
            except Exception as e:
                logger.error(f"{self.name}: Failed to apply power {applied} ({source}): {e}")
            st['last_applied_power'] = float(applied)

        self._applied_power = float(applied)
        self._guard_state = self._reason_to_guard_state(reason)
        self._guard_remaining_sec = int(remaining_sec)
        self._status_text = self._build_status_text()

        last_reason = st.get('last_reason', None)
        if last_reason != reason:
            if reason.startswith("Hold"):
                logger.debug(f"{self.name}: PowerGuard {reason} (req={requested_power}, applied={applied})")
            else:
                logger.info(f"{self.name}: PowerGuard {reason} (req={requested_power}, applied={applied})")
            st['last_reason'] = reason

        return float(applied)

    async def run(self):
        await asyncio.sleep(5)
        while True:
            if self.name != "System":
                output = 0.0
                primary_temp = self.sensor.temp()
                fridge_temp = self.fridge_sensor.temp() if self.fridge_sensor is not None else None
                sensor_stale = self._sensor_is_stale(self.sensor)

                if sensor_stale:
                    if not self._stale_sensor_fault_active:
                        logger.error(
                            f"{self.name}: Primary sensor data is stale; forcing output OFF until fresh data returns"
                        )
                        self._stale_sensor_fault_active = True
                else:
                    if self._stale_sensor_fault_active:
                        logger.info(f"{self.name}: Primary sensor data is fresh again; automatic control resumed")
                        self._stale_sensor_fault_active = False

                if self.enabled:
                    if self._autoMode:
                        if sensor_stale:
                            output = 0.0
                            self._set_power_guarded(0.0, source='stale-sensor', force=True)
                        else:
                            if self.logic.__class__.__name__ == "DualLoopLogic":
                                inputs = {
                                    'BeerSensor': primary_temp,
                                    'FridgeSensor': fridge_temp
                                }
                                output = self.logic.calc(inputs, self.targetTemp)
                            else:
                                output = self.logic.calc(primary_temp, self.targetTemp)

                            output = self._set_power_guarded(output, source='auto', current_temp=primary_temp)
                    else:
                        # In Manual mode, keep re-evaluating the saved manual request through PowerGuard
                        output = self._set_power_guarded(
                            self._requested_power,
                            source='manual-hold',
                            current_temp=primary_temp
                        )
                else:
                    output = 0.0
                    self._requested_power = 0.0
                    self._applied_power = float(self.actor.getPower()) if self.actor is not None else 0.0
                    self._guard_state = "DISABLED"
                    self._guard_remaining_sec = 0
                    self._status_text = self._build_status_text()

                self.timestamp_history.append(time())
                self.power_history.append(output)
                self.temp_history.append(primary_temp)
                self.setpoint_history.append(self.targetTemp)
                self.fridge_temp_history.append(fridge_temp)
                self.gravity_history.append(self.sensor.gravity())
                self.abv_history.append(self.sensor.abv())
                self.atten_history.append(self.sensor.atten())
                self.ograv_history.append(self.sensor.ograv())

                if len(self.timestamp_history) == HISTORY_SIZE + 1:
                    i = self.mostredundanttime(self.timestamp_history)
                    del self.timestamp_history[i]
                    del self.power_history[i]
                    del self.temp_history[i]
                    del self.setpoint_history[i]
                    del self.fridge_temp_history[i]
                    del self.gravity_history[i]
                    del self.abv_history[i]
                    del self.atten_history[i]
                    del self.ograv_history[i]

                self.broadcastDetails()
                self.save_history()

            await asyncio.sleep(10)

    async def websocket_handler(self, session, msg, additional_argument=None, *args):
        try:
            session_info = str(session)
        except Exception as e:
            logger.error(f"Error inspecting session object: {e}")
            session_info = "unknown"

        if isinstance(additional_argument, sockjs.protocol.SockjsMessage):
            if additional_argument.type == sockjs.protocol.MsgType.OPEN:
                self.broadcastDetails()
            elif additional_argument.type == sockjs.protocol.MsgType.MESSAGE:
                try:
                    data = json.loads(additional_argument.data)
                    for endpoint, value in data.items():
                        self.callback(endpoint, value)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Failed to decode WebSocket message: session={session}, "
                        f"controller={self.name}, error={e}, raw_data={additional_argument.data}"
                    )


async def listControllers(request):
    res = request.app.router['controllerDetail']
    controllers = {
        name: {'url': str(request.url.with_path(str(res.url_for(name=name))))}
        for name, component in components.items()
        if isinstance(component, Controller)
    }
    system_url = str(request.url.with_path('/controllers/System'))
    controllers['System'] = {'url': system_url}
    return web.json_response(controllers)


async def controllerDetail(request):
    try:
        controllerName = request.match_info['name']
        details = components[controllerName].getDetails()

        for key, value in details.items():
            if isinstance(value, decimal.Decimal):
                details[key] = float(value)

        return web.json_response(details)
    except KeyError as e:
        raise web.HTTPNotFound(reason=f'Unknown controller {str(e)}')


async def dataHistory(request):
    try:
        controllerName = request.match_info['name']
        controller = components[controllerName]
        data = {
            'label': list(controller.timestamp_history),
            'temperature': [float(temp) if isinstance(temp, decimal.Decimal) else temp for temp in controller.temp_history],
            'power': [float(power) if isinstance(power, decimal.Decimal) else power for power in controller.power_history],
            'setpoint': [float(setpoint) if isinstance(setpoint, decimal.Decimal) else setpoint for setpoint in controller.setpoint_history],
            'fridgeTemperature': [float(temp) if isinstance(temp, decimal.Decimal) else temp for temp in controller.fridge_temp_history],
            'gravity': [float(gravity) if isinstance(gravity, decimal.Decimal) else gravity for gravity in controller.gravity_history],
            'abv': [float(abv) if isinstance(abv, decimal.Decimal) else abv for abv in controller.abv_history],
            'atten': [float(atten) if isinstance(atten, decimal.Decimal) else atten for atten in controller.atten_history],
            'ograv': [float(ograv) if isinstance(ograv, decimal.Decimal) else ograv for ograv in controller.ograv_history]
        }
        return web.json_response(data)
    except KeyError as e:
        raise web.HTTPNotFound(reason=f'Unknown controller {str(e)}')


app.router.add_get('/controllers', listControllers)
app.router.add_get('/controllers/{name}', controllerDetail, name='controllerDetail')
app.router.add_get('/controllers/{name}/datahistory', dataHistory, name='dataHistory')
