# filename: event.py

import asyncio
import logging
from collections import namedtuple

logger = logging.getLogger(__name__)

Event = namedtuple('Event', ['source', 'endpoint', 'data'])

def name(event):
    return f"{event.source}.{event.endpoint}"

Event.name = name

observers = {}

def register(eventName, callback):
    observers.setdefault(eventName, []).append(callback)

def notify(event):
    logger.debug(f"notify {event}")
    if event.name() in observers:
        for observer in observers[event.name()]:
            if asyncio.iscoroutinefunction(observer):
                asyncio.ensure_future(observer(event.data))
            else:
                observer(event.data)

