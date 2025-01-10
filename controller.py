# filename: controller.py

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
from time import time

import event
import interfaces
import syscontroller
from common import app, components

logger = logging.getLogger(__name__)

HISTORY_SIZE = 1440
HISTORY_FILE_PATH = '/home/pi/tfdeux/history'  # Set a proper path for history files

class Controller(interfaces.Component, interfaces.Runnable):
    def __init__(self, name, sensor, actor, logic, targetTemp=0.0, initiallyEnabled=False, reload_history='no'):
        self.w1sensor = components.get('Onewire')
        self.name = name
        self._enabled = initiallyEnabled
        self._autoMode = True
        self.sensor = sensor
        self.actor = actor
        self.targetTemp = targetTemp
        self.logic = logic
        self.timestamp_history = []
        self.power_history = []
        self.temp_history = []
        self.setpoint_history = []
        self.w1temp_history = []
        self.gravity_history = []
        self.abv_history = []
        self.atten_history = []
        self.ograv_history = []
        self.history_file = os.path.join(HISTORY_FILE_PATH, f'{name}_history.json')

        if reload_history.lower() == 'yes':
            self.load_history()  # Load history on initialization
        
        sockjs.add_endpoint(app, prefix=f'/controllers/{self.name}/ws', name=f'{self.name}-ws', handler=self.websocket_handler)
        asyncio.ensure_future(self.run())

        event.notify(event.Event(source=self.name, endpoint='initialSetpoint', data=self.targetTemp))
        event.notify(event.Event(source=self.name, endpoint='enabled', data=self._enabled))
        event.notify(event.Event(source=self.name, endpoint='automatic', data=self._autoMode))

    def callback(self, endpoint, data):
        includeSetpoint = True
        if self.name == "System":
            syscontroller.handle_system_command(endpoint, data, controller_name=self.name)
        elif endpoint in ['state', 'enabled']:
            self.enabled = bool(data)
            self.actor.updatePower(0.0)
            state_text = "ENABLED" if bool(data) else "DISABLED"
            logger.info(f"Setting controller {self.name} to {state_text}")
        elif endpoint == 'automatic':
            self.actor.updatePower(0.0)
            self.automatic = bool(data)
            mode_text = "AUTOMATIC" if self._autoMode else "MANUAL"
            logger.info(f"Setting controller {self.name} to {mode_text}")
        elif endpoint == 'setpoint':
            self.setSetpoint(float(data))
            includeSetpoint = True
        elif endpoint == 'power':
            self.actor.updatePower(float(data))
            logger.debug(f"Setting {self.name} controller power to {float(data)}")
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
            self.actor.updatePower(0.0)
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
                'wsUrl': f'/controllers/{self.name}/ws'
            }
        else:
            details = {
                'name': self.name,
                'temperature': self.sensor.temp(),
                'w1temperature': self.w1sensor.temp(),
                'gravity': self.sensor.gravity(),
                'abv': self.sensor.abv(),
                'atten': self.sensor.atten(),
                'ograv': self.sensor.ograv(),
                'enabled': self.enabled,
                'automatic': self.automatic,
                'power': self.actor.getPower(),
                'setpoint': self.targetTemp,
                'wsUrl': f'/controllers/{self.name}/ws'
            }

        # Convert Decimal to float for JSON serialization
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
        """Save current history to a JSON file."""
        def convert_decimal(value):
            """Convert Decimal to float, recursively handle lists and dictionaries."""
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
            'w1temperature': self.w1temp_history,
            'gravity': self.gravity_history,
            'abv': self.abv_history,
            'atten': self.atten_history,
            'ograv': self.ograv_history
        }

        # Convert Decimal values to float before saving
        data = convert_decimal(data)

        try:
            with open(self.history_file, 'w') as file:
                json.dump(data, file)
        except Exception as e:
            logger.error(f"Failed to save history for {self.name}: {e}")

    def load_history(self):
        """Load history from a JSON file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as file:
                    data = json.load(file)
                self.timestamp_history = data.get('timestamp', [])
                self.power_history = data.get('power', [])
                self.temp_history = data.get('temperature', [])
                self.setpoint_history = data.get('setpoint', [])
                self.w1temp_history = data.get('w1temperature', [])
                self.gravity_history = data.get('gravity', [])
                self.abv_history = data.get('abv', [])
                self.atten_history = data.get('atten', [])
                self.ograv_history = data.get('ograv', [])
        except Exception as e:
            logger.error(f"Failed to load history for {self.name}: {e}")

    async def run(self):
        await asyncio.sleep(5)
        while True:
            # Skip actor and sensor logic if the controller is System
            if self.name != "System":
                output = self.actor.getPower()
                if self.enabled:
                    if self._autoMode:
                        output = self.logic.calc(self.sensor.temp(), self.targetTemp)
                    self.actor.updatePower(output)
    
                # Update histories for controllers with actors
                self.timestamp_history.append(time())
                self.power_history.append(output)
                self.temp_history.append(self.sensor.temp())
                self.setpoint_history.append(self.targetTemp)
                self.w1temp_history.append(self.w1sensor.temp())
                self.gravity_history.append(self.sensor.gravity())
                self.abv_history.append(self.sensor.abv())
                self.atten_history.append(self.sensor.atten())
                self.ograv_history.append(self.sensor.ograv())
    
                # Cull histories if they exceed the size limit
                if len(self.timestamp_history) == HISTORY_SIZE + 1:
                    i = self.mostredundanttime(self.timestamp_history)
                    del self.timestamp_history[i]
                    del self.power_history[i]
                    del self.temp_history[i]
                    del self.setpoint_history[i]
                    del self.w1temp_history[i]
                    del self.gravity_history[i]
                    del self.abv_history[i]
                    del self.atten_history[i]
                    del self.ograv_history[i]
    
                # Always broadcast details for all controllers, including System
                self.broadcastDetails()
                self.save_history()  # Save history periodically
    
            await asyncio.sleep(10)

    async def websocket_handler(self, session, msg, additional_argument=None, *args):
        try:
            session_info = str(session)  # Fallback to string representation
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
                    logger.error(f"Failed to decode WebSocket message: session={session}, controller={self.name}, error={e}, raw_data={additional_argument.data}")

async def listControllers(request):
    res = request.app.router['controllerDetail']
    controllers = {name: {'url': str(request.url.with_path(str(res.url_for(name=name))))} for name, component in components.items() if isinstance(component, Controller)}
    system_url = str(request.url.with_path('/controllers/System'))
    controllers['System'] = {'url': system_url}
    return web.json_response(controllers)

async def controllerDetail(request):
    try:
        controllerName = request.match_info['name']
        details = components[controllerName].getDetails()

        # Convert Decimal to float for JSON serialization
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
            'w1temperature': [float(temp) if isinstance(temp, decimal.Decimal) else temp for temp in controller.w1temp_history],
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

