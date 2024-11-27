# filename: tfbrew.py

import sys
import os
import importlib
import logging
import asyncio
from aiohttp import web
from ruamel.yaml import YAML

import interfaces
import controller
import event
from common import app, components

yaml = YAML(typ='safe')
configFile = 'config.yaml'
if len(sys.argv) > 1:
    configFile = sys.argv[1]
print(f"Using config from {configFile}")

config = yaml.load(open(configFile, mode='r'))

logLevel = getattr(logging, config.get('logLevel', 'WARNING').upper(), logging.WARNING)
logging.basicConfig(level=logLevel, format='%(asctime)s:%(levelname)s:%(name)s:%(message)s', filename='tfbrew.log', filemode='w+')
logger = logging.getLogger(__name__)
console = logging.StreamHandler()
console.setLevel(config.get('consoleLoglevel', 'WARNING'))
logging.getLogger('').addHandler(console)
logging.getLogger('aiohttp.access').setLevel(logging.ERROR)  # Suppress access logs

sys.path.append(os.path.join(os.path.dirname(__file__), "plugins"))

for conn in config['connections']:
    sendEvent, recvEvent = conn.split('=>')
    sendComponent, sendType = sendEvent.split('.')
    recvComponent, recvType = recvEvent.split('.')
    event.register(sendEvent, lambda event, rc=recvComponent, rt=recvType: components[rc].callback(rt, event))

for componentType in ['sensors', 'actors', 'extensions']:
    for component in config[componentType]:
        for name, attribs in component.items():
            logger.info(f"Setting up {componentType}: {name}")
            plugin = importlib.import_module(f'plugins.{attribs["plugin"]}')
            components[name] = plugin.factory(name, attribs)

for ctrl in config['controllers']:
    for name, attribs in ctrl.items():
        logger.info(f"Setting up controller: {name}")
        logicPlugin = importlib.import_module(f'plugins.{attribs["plugin"]}')
        logic = logicPlugin.factory(name, attribs['logicCoeffs'])
        sensor = components[attribs['sensor']]
        actor = components[attribs['actor']]
        initialSetpoint = attribs.get('initialSetpoint', 67.0)
        initiallyEnabled = True if attribs.get('initialState', 'on') == 'on' else 'off'
        components[name] = controller.Controller(name, sensor, actor, logic, initialSetpoint, initiallyEnabled)

async def start_background_tasks(app):
    pass

async def cleanup_background_tasks(app):
    pass

app.on_startup.append(start_background_tasks)
app.on_cleanup.append(cleanup_background_tasks)

isWebUIenabled = config.get('enableWebUI', False)
async def rootRouteHandler(request):
    if isWebUIenabled:
        return web.HTTPFound('/static/index.html')
    else:
        return web.Response(text="Web UI not enabled in config.yaml")

app.router.add_get('/', rootRouteHandler)

if isWebUIenabled:
    app.router.add_static('/static', 'static/')

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    web.run_app(app, port=config.get('port', 8080), loop=loop)

for route in app.router.routes():
    if hasattr(route, 'handler'):
        print(f"Method: {route.method}, Path: {route._path}, Handler: {route.handler}")

