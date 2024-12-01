# filename: SimpleWebView.py

import asyncio
import logging
import struct
import sys
import time
from aiohttp import web
from functools import partial

import interfaces
from common import app
from event import notify, Event

logger = logging.getLogger(__name__)

def factory(name, settings):
    logger.info("Initializing SimpleWebView")
    endpoints = settings.get('endpoints', {})
    return SimpleWebView(name, endpoints)

class SimpleWebView(interfaces.Component):
    def __init__(self, name, endpoints):
        self.name = name
        self.endpointData = {}
        app.router.add_get('/simpleview', self.webView)

        for name in endpoints:
            app.router.add_put("/%s"%name, partial(self.handler, name))

    def callback(self, endpoint, data):
        self.endpointData[endpoint] = data

    async def handler(self, name, request):
        stuff = await request.json()
        notify(Event(source=self.name, endpoint=name, data=stuff))
        return web.json_response(stuff)

    def webView(self, request):
        return web.json_response(self.endpointData)
