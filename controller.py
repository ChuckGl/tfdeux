# filename: controller.py

import os
import sys
import asyncio
import logging
import json
import sockjs
import subprocess
import decimal
from time import time
from aiohttp import web

import interfaces
import event
from common import app, components
from plugins.W1Sensor import W1Sensor
from plugins.DummySensor import DummySensor

logger = logging.getLogger(__name__)

HISTORY_SIZE = 1440

class Controller(interfaces.Component, interfaces.Runnable):
    def __init__(self, name, sensor, actor, logic, targetTemp=0.0, initiallyEnabled=False):
        self.w1sensor = W1Sensor(name='Onewire', sensorId='28-0300a279cd1d')
        #self.w1sensor = DummySensor(name='Onewire', fakeTemp=50, fakeGravity=0.0, sensor_type='thermo')
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
        print_registered_routes()
        asyncio.ensure_future(self.run())

        event.notify(event.Event(source=self.name, endpoint='initialSetpoint', data=self.targetTemp))
        event.notify(event.Event(source=self.name, endpoint='enabled', data=self._enabled))
        event.notify(event.Event(source=self.name, endpoint='automatic', data=self._autoMode))

    def callback(self, endpoint, data):
        includeSetpoint = True
        if endpoint in ['state', 'enabled']:
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
            output = self.actor.getPower()
            if self.enabled:
                if self._autoMode:
                    output = self.logic.calc(self.sensor.temp(), self.targetTemp)
                self.actor.updatePower(output)

            self.broadcastDetails()

            self.timestamp_history.append(time())
            self.power_history.append(output)
            self.temp_history.append(self.sensor.temp())
            self.setpoint_history.append(self.targetTemp)
            self.w1temp_history.append(self.w1sensor.temp())
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
                del self.w1temp_history[i]
                del self.gravity_history[i]
                del self.abv_history[i]
                del self.atten_history[i]
                del self.ograv_history[i]

            await asyncio.sleep(10)

    async def websocket_handler(self, session, msg, additional_argument=None, *args):
        try:
            session_info = str(session)  # Fallback to string representation
            logger.info(f"WebSocket Handler invoked for: {self.name} (session={session_info})")
        except Exception as e:
            logger.error(f"Error inspecting session object: {e}")
            session_info = "unknown"

        if isinstance(additional_argument, sockjs.protocol.SockjsMessage):
            if additional_argument.type == sockjs.protocol.MsgType.OPEN:
                logger.info(f"WebSocket OPEN: session={session}, controller={self.name}")
                self.broadcastDetails()
                logger.info(f"Broadcasting details on WebSocket OPEN for: {self.name}")
            elif additional_argument.type == sockjs.protocol.MsgType.MESSAGE:
                logger.info(f"WebSocket MESSAGE received: session={session}, controller={self.name}, raw_data={additional_argument.data}")
                try:
                    data = json.loads(additional_argument.data)
                    for endpoint, value in data.items():
                        logger.info(f"Processing message from WebSocket: session={session}, controller={self.name}, endpoint={endpoint}, value={value}")
                        self.callback(endpoint, value)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode WebSocket message: session={session}, controller={self.name}, error={e}, raw_data={additional_argument.data}")

async def listControllers(request):
    print("listControllers called!")
    res = request.app.router['controllerDetail']
    controllers = {name: {'url': str(request.url.with_path(str(res.url_for(name=name))))} for name, component in components.items() if isinstance(component, Controller)}
    system_url = str(request.url.with_path('/controllers/System'))
    controllers['System'] = {'url': system_url}
    print("CONTROLLER LIST:", controllers)
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

async def system_handler(session, msg, additional_argument=None, *args):
    if isinstance(additional_argument, sockjs.protocol.SockjsMessage):
        if additional_argument.type == sockjs.protocol.MsgType.OPEN:
            pass
        elif additional_argument.type == sockjs.protocol.MsgType.MESSAGE:
            if additional_argument.data == "reboot":
                os.system('sudo shutdown -r')
                logger.info("***** System Rebooting in 1 minute, use sudo shutdown -c to cancel *****")
            elif additional_argument.data == "poweroff":
                os.system('sudo shutdown -P')
                logger.info("***** System Powering Off in 1 minute, use sudo shutdown -c to cancel *****")
            else:
                logger.info("Unknown command received from System Admin WebSocket")

        elif additional_argument.type == sockjs.protocol.MsgType.CLOSE:
            pass

def print_registered_routes():
    print("Registered routes:")
    for route in app.router.routes():
        if hasattr(route, 'handler'):
            print(f"Method: {route.method}, Path: {route.resource}, Handler: {route.handler}")
        else:
            print(f"Path: {route.resource}")


app.router.add_get('/controllers', listControllers)
app.router.add_get('/controllers/{name}', controllerDetail, name='controllerDetail')
app.router.add_get('/controllers/{name}/datahistory', dataHistory, name='dataHistory')

#sockjs.add_endpoint(app, Controller.websocket_handler, name='system', prefix='/controllers/System/ws')

sockjs.add_endpoint(app, prefix=f'/controllers/System/ws', name=f'System', handler=Controller.websocket_handler)
print_registered_routes()
