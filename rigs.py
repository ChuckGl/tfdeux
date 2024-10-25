# filename: rigs.py

import asyncio
import decimal
import event
import interfaces
import json
import logging
import sockjs
from aiohttp import web
from common import app, components

logger = logging.getLogger(__name__)

class Rig:
    def __init__(self, name, controllers):
        self.name = name
        self.controllers = controllers
        for controller in self.controllers:
            controller.rig = self
        sockjs.add_endpoint(app, prefix=f'/rigs/{self.name}/ws', name=f'{self.name}-ws', handler=self.websocketHandler)
        asyncio.ensure_future(self.run())

    def getRigDetails(self):
        aggregated_data = {}
        for ctrl in self.controllers:
            details = ctrl.getDetails()
            logger.debug(f"Collecting details from {ctrl.name}: {details}")
            aggregated_data[ctrl.name] = details

        # Convert Decimal to float for JSON serialization
        for key, value in aggregated_data.items():
            if isinstance(value, decimal.Decimal):
                aggregated_data[key] = float(value)

        return aggregated_data

    def combineRigDetails(self):
        combined_details = {
            'name': self.name,
            'temperature': None,
            'w1temperature': None,
            'gravity': None,
            'abv': None,
            'atten': None,
            'ograv': None,
            'enabled': None,
            'automatic': None,
            'power': None,
            'setpoint': None,
            'heater_enabled': None,
            'heater_automatic': None,
            'heater_power': None,
            'heater_setpoint': None,
            'wsUrl': f'/rigs/{self.name}/ws',
        }

        for ctrl in self.controllers:
            if ctrl.name == 'Fridge':
                fridge_data = ctrl.getDetails()
                combined_details.update({
                    'temperature': fridge_data.get('temperature'),
                    'w1temperature': fridge_data.get('w1temperature'),
                    'gravity': fridge_data.get('gravity'),
                    'abv': fridge_data.get('abv'),
                    'atten': fridge_data.get('atten'),
                    'ograv': fridge_data.get('ograv'),
                    'enabled': fridge_data.get('enabled'),
                    'automatic': fridge_data.get('automatic'),
                    'power': fridge_data.get('power'),
                    'setpoint': fridge_data.get('setpoint')
                })
            elif ctrl.name == 'Heater':
                heater_data = ctrl.getDetails()
                combined_details.update({
                    'heater_enabled': heater_data.get('enabled'),
                    'heater_automatic': heater_data.get('automatic'),
                    'heater_power': heater_data.get('power'),
                    'heater_setpoint': heater_data.get('setpoint')
                })

        return combined_details

    async def getRigDataHistory(self):
        aggregated_history = {}
        for ctrl in self.controllers:
            aggregated_history[ctrl.name] = {
                'label': list(ctrl.timestamp_history),
                'temperature': [float(temp) for temp in ctrl.temp_history],
                'power': [float(power) for power in ctrl.power_history],
                'setpoint': [float(setpoint) for setpoint in ctrl.setpoint_history],
                'w1temperature': [float(temp) for temp in ctrl.w1temp_history],
                'gravity': [float(gravity) for gravity in ctrl.gravity_history],
                'abv': [float(abv) for abv in ctrl.abv_history],
                'atten': [float(atten) for atten in ctrl.atten_history],
                'ograv': [float(ograv) for ograv in ctrl.ograv_history],
            }
        return aggregated_history

    async def combineRigDataHistory(self):
        combined_history = {
            'label': [],
            'temperature': [],
            'power': [],
            'setpoint': [],
            'w1temperature': [],
            'gravity': [],
            'abv': [],
            'atten': [],
            'ograv': []
        }

        fridge_data, heater_data = {}, {}

        for ctrl in self.controllers:
            if ctrl.name == 'Fridge':
                fridge_data = {
                    'label': list(ctrl.timestamp_history),
                    'temperature': [float(temp) for temp in ctrl.temp_history],
                    'power': [float(power) for power in ctrl.power_history],
                    'setpoint': [float(setpoint) for setpoint in ctrl.setpoint_history],
                    'w1temperature': [float(temp) for temp in ctrl.w1temp_history],
                    'gravity': [float(gravity) for gravity in ctrl.gravity_history],
                    'abv': [float(abv) for abv in ctrl.abv_history],
                    'atten': [float(atten) for atten in ctrl.atten_history],
                    'ograv': [float(ograv) for ograv in ctrl.ograv_history]
                }
            elif ctrl.name == 'Heater':
                heater_data = {
                    'power': [float(power) for power in ctrl.power_history],
                    'setpoint': [float(setpoint) for setpoint in ctrl.setpoint_history]
                }

        if fridge_data:
            combined_history.update(fridge_data)
        if heater_data:
            combined_history.update({
                'heater_power': heater_data['power'],
                'heater_setpoint': heater_data['setpoint']
            })

        return combined_history

    def broadcastDetails(self, includeSetpoint=True):
        manager = sockjs.get_manager(f'{self.name}-ws', app)
        details = self.combineRigDetails()
        if not includeSetpoint:
            details.pop('setpoint', None)
        manager.broadcast(details)

    async def websocketHandler(self, session, msg, additional_argument=None, *args):
        if isinstance(additional_argument, sockjs.protocol.SockjsMessage):
            if additional_argument.type == sockjs.protocol.MsgType.OPEN:
                self.broadcastDetails()
            elif additional_argument.type == sockjs.protocol.MsgType.MESSAGE:
                data = json.loads(additional_argument.data)
                controllerName = data.pop('controller', None)
                controllerInstance = components.get(controllerName)
                if controllerInstance:
                    for endpoint, value in data.items():
                        controllerInstance.callback(endpoint, value)
                else:
                    logger.error(f"Unknown controller: {controllerName}")

    async def run(self):
        await asyncio.sleep(5)
        while True:
            self.broadcastDetails()
            await asyncio.sleep(10)

async def listRigs(request):
    res = request.app.router['rigDetail']
    rigs = {name: {'url': str(request.url.with_path(str(res.url_for(name=name))))}
            for name, component in components.items() if isinstance(component, Rig)}
    return web.json_response(rigs)

async def rigDetail(request):
    try:
        rigName = request.match_info['name']
        details = components[rigName].combineRigDetails()

        # Convert Decimal to float for JSON serialization
        for key, value in details.items():
            if isinstance(value, decimal.Decimal):
                details[key] = float(value)

        return web.json_response(details)
    except KeyError as e:
        raise web.HTTPNotFound(reason=f'Unknown rig {str(e)}')

async def rigDataHistory(request):
    try:
        rigName = request.match_info['name']
        history = await components[rigName].combineRigDataHistory()

        # Convert Decimal to float for JSON serialization
        for key, value in history.items():
            if isinstance(value, decimal.Decimal):
                history[key] = float(value)

        return web.json_response(history)
    except KeyError as e:
        raise web.HTTPNotFound(reason=f'Unknown rig {str(e)}')

# Define routes for rigs
app.router.add_get('/rigs', listRigs)
app.router.add_get('/rigs/{name}', rigDetail, name='rigDetail')
app.router.add_get('/rigs/{name}/datahistory', rigDataHistory, name='rigDataHistory')

