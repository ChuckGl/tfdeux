# filename: common.py

import asyncio
from aiohttp import web

components = {}

loop = asyncio.get_event_loop()
app = web.Application(loop=loop)

__all__ = ['app', 'loop']

