# filename: BLEScanner.py

import aioblescan as aiobs
import asyncio
import logging
from typing import Callable, List

logger = logging.getLogger(__name__)

PacketHandler = Callable[[bytes], None]

class BLEScanner:
    _instance = None

    def __init__(self, dev_id: int = 0):
        self.dev_id = dev_id
        self.sock = None
        self.conn = None
        self.btctrl = None
        self.handlers: List[PacketHandler] = []
        self._task = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = BLEScanner()
        return cls._instance

    def register(self, handler: PacketHandler):
        if handler not in self.handlers:
            self.handlers.append(handler)

    async def start(self):
        # Start once
        if self._task is not None:
            return

        try:
            self.sock = aiobs.create_bt_socket(self.dev_id)
            logger.info("BLEScanner: Created Bluetooth socket")
        except OSError as e:
            logger.error(f"BLEScanner: Unable to create socket - {e}")
            raise

        self._task = asyncio.get_event_loop().create_task(self._run())

    async def _shutdown(self):
        logger.info("BLEScanner: shutting down scan...")
        try:
            if self.btctrl:
                await self.btctrl.stop_scan_request()
        except Exception as e:
            logger.error(f"BLEScanner: stop_scan_request error: {e}")
        finally:
            if self.conn:
                self.conn.close()
                self.conn = None
            logger.info("BLEScanner: shutdown complete")

    async def _run(self):
        loop = asyncio.get_running_loop()

        # Matches your existing TiltSensor pattern (Python 3.11)
        self.conn, self.btctrl = await loop._create_connection_transport(
            self.sock, aiobs.BLEScanRequester, None, None
        )

        def _dispatch(data: bytes):
            for h in self.handlers:
                try:
                    h(data)
                except Exception as e:
                    key = (id(h), str(e))
                    if key not in handler_errors:
                        handler_errors.add(key)
                        logger.error(f"BLEScanner: handler error (first occurrence): {e}")

        self.btctrl.process = _dispatch

        # CRITICAL: active scan so we get SCAN_RSP (Inkbird TH2 temp is in SCAN_RSP)
        await self.btctrl.send_scan_request(isactivescan=True)

        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

