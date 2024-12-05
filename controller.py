# filename: controller.py

import json
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

class Controller(interfaces.Component, interfaces.Runnable):
    def __init__(self, name, sensor, actor, logic, targetTemp=0.0, initiallyEnabled=False):
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
            logger.info(f"Setting {self.name} controller enabled to {bool(data)}")
        elif endpoint == 'automatic':
            self.actor.updatePower(0.0)
            self.automatic = bool(data)
            logger.info(f"Setting {self.name} controller automatic to {bool(self._autoMode)}")
        elif endpoint == 'setpoint':
            self.setSetpoint(float(data))
            includeSetpoint = True
        elif endpoint == 'power':
            self.actor.updatePower(float(data))
            logger.info(f"Setting {self.name} controller power to {float(data)}")
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

# Create a SystemController class extending Controller
class SystemController(Controller):
    def __init__(self, name="System"):
        current_time = datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        super().__init__(name, sensor=None, actor=None, logic=None)
        
        # Register WebSocket route only if not already registered
        existing_routes = [route for route in app.router.routes()]
        if not any(route for route in existing_routes if f'/controllers/{self.name}/ws' in str(route.resource)):
            sockjs.add_endpoint(app, prefix=f'/controllers/{self.name}/ws', name=f'{self.name}-ws', handler=self.websocket_handler)
        else:
            current_time = datetime.fromtimestamp(time()).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        
        # Broadcast details on initialization
        self.broadcastDetails()

    def callback(self, endpoint, data):
        # Handle specific System commands
        if endpoint == "admin":
            if data == "reboot":
                logger.info("System: Reboot command received.")
                os.system('sudo shutdown -r')
                event.notify(event.Event(source=self.name, endpoint='admin', data='rebooting'))
            elif data == "poweroff":
                logger.info("System: Poweroff command received.")
                os.system('sudo shutdown -P')
                event.notify(event.Event(source=self.name, endpoint='admin', data='powering_off'))
            else:
                logger.warning(f"System: Unknown command received: {data}")
        else:
            logger.warning(f"System: Unhandled endpoint {endpoint} with data {data}")

    def getDetails(self):
        # Provide basic details for the System
        return {
            'name': self.name,
            'wsUrl': f'/controllers/{self.name}/ws',
        }

    def broadcastDetails(self):
        # Broadcast System details
        manager = sockjs.get_manager(f'{self.name}-ws', app)
        details = self.getDetails()
        manager.broadcast(details)

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

