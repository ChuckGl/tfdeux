# filename: BLEScanner.py 01APR2026 0737am

import aioblescan as aiobs
import asyncio
import logging
import time
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

PacketHandler = Callable[[bytes], None]


class BLEScanner:
    _instance = None

    # Recovery tuning
    RECONNECT_DELAY_SEC = 5
    HEALTH_CHECK_INTERVAL_SEC = 5
    INACTIVITY_TIMEOUT_SEC = 60

    # Lightweight heartbeat logging
    HEARTBEAT_LOG_INTERVAL_SEC = 60

    def __init__(self, dev_id: int = 0):
        self.dev_id = dev_id
        self.sock = None
        self.conn = None
        self.btctrl = None
        self.handlers: List[PacketHandler] = []
        self._task: Optional[asyncio.Task] = None
        self._handler_errors = set()

        self._last_packet_monotonic = 0.0
        self._scan_started_monotonic = 0.0
        self._last_heartbeat_log_monotonic = 0.0

        self._restart_count = 0
        self._session_count = 0

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = BLEScanner()
        return cls._instance

    def register(self, handler: PacketHandler):
        if handler not in self.handlers:
            self.handlers.append(handler)
            logger.info(
                f"BLEScanner: registered handler {getattr(handler, '__qualname__', repr(handler))}"
            )

    async def start(self):
        # Already running
        if self._task is not None and not self._task.done():
            return

        # Clean up any completed/failed task state before restarting
        if self._task is not None and self._task.done():
            try:
                exc = self._task.exception()
                if exc is not None:
                    logger.error(f"BLEScanner: previous scanner task exited with exception: {exc}")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"BLEScanner: unable to inspect previous task exception: {e}")
            self._task = None

        logger.info("BLEScanner: starting supervisor task")
        self._task = asyncio.get_running_loop().create_task(self._run(), name="BLEScanner._run")
        self._task.add_done_callback(self._task_done)

    def _task_done(self, task: asyncio.Task):
        try:
            if task.cancelled():
                logger.info("BLEScanner: supervisor task cancelled")
            else:
                exc = task.exception()
                if exc is not None:
                    logger.error(f"BLEScanner: supervisor task exited with exception: {exc}", exc_info=exc)
                else:
                    logger.warning("BLEScanner: supervisor task exited normally")
        except Exception as e:
            logger.error(f"BLEScanner: error inspecting completed task: {e}")
        finally:
            self._task = None

    async def _shutdown(self):
        logger.info("BLEScanner: shutting down scan...")
        try:
            if self.btctrl:
                try:
                    await self.btctrl.stop_scan_request()
                    logger.info("BLEScanner: stop_scan_request completed")
                except Exception as e:
                    logger.error(f"BLEScanner: stop_scan_request error: {e}")
        finally:
            try:
                if self.conn:
                    self.conn.close()
            except Exception as e:
                logger.error(f"BLEScanner: conn.close error: {e}")

            try:
                if self.sock:
                    self.sock.close()
            except Exception as e:
                logger.error(f"BLEScanner: sock.close error: {e}")

            self.conn = None
            self.btctrl = None
            self.sock = None
            self._last_packet_monotonic = 0.0
            self._scan_started_monotonic = 0.0
            self._last_heartbeat_log_monotonic = 0.0
            logger.info("BLEScanner: shutdown complete")

    async def _open_transport(self):
        loop = asyncio.get_running_loop()

        self.sock = aiobs.create_bt_socket(self.dev_id)
        logger.info(f"BLEScanner: created Bluetooth socket on hci{self.dev_id}")

        # Matches your existing TiltSensor pattern (Python 3.11)
        self.conn, self.btctrl = await loop._create_connection_transport(
            self.sock, aiobs.BLEScanRequester, None, None
        )
        logger.info("BLEScanner: BLE transport created")

        def _dispatch(data: bytes):
            self._last_packet_monotonic = time.monotonic()

            # Temporary Ruuvi debug logging
            try:
                ev = aiobs.HCI_Event()
                ev.decode(data)

                manufacturer_data = ev.retrieve("Manufacturer Specific Data")
                if manufacturer_data:
                    for entry in manufacturer_data:
                        try:
                            payload_bytes = entry.payload[1].val
                        except Exception:
                            continue

                        if not payload_bytes or len(payload_bytes) < 2:
                            continue

                        # Check for Ruuvi manufacturer ID 0x0499
                        if payload_bytes[0] == 0x99 and payload_bytes[1] == 0x04:
                            peer_values = ev.retrieve("peer")
                            peer_mac = peer_values[0].val if peer_values else "unknown"

                            rssi_values = ev.retrieve("rssi")
                            rssi = rssi_values[-1].val if rssi_values else None

                            payload_mac = "unavailable"
                            # RAWv2 payload layout includes MAC bytes near the end
                            # Require enough length before extracting bytes 18:24
                            if len(payload_bytes) >= 26:
                                payload_mac = ':'.join(f'{b:02x}' for b in payload_bytes[20:26])

                            logger.info(
                                f"RUUVI DEBUG -> peer: {peer_mac} | payload: {payload_mac} | rssi: {rssi}"
                            )
                        # Only log first matching Ruuvi entry per packet
                            break

            except Exception as e:
                logger.error(f"RUUVI DEBUG ERROR: {e}")

            for h in self.handlers:
                try:
                    h(data)
                except Exception as e:
                    key = (id(h), str(e))
                    if key not in self._handler_errors:
                        self._handler_errors.add(key)
                        logger.error(
                            f"BLEScanner: handler error in {getattr(h, '__qualname__', repr(h))}: {e}",
                            exc_info=True
                        )

        self.btctrl.process = _dispatch

        # CRITICAL: active scan so we get SCAN_RSP (Inkbird TH2 temp is in SCAN_RSP)
        await self.btctrl.send_scan_request(isactivescan=True)

        now = time.monotonic()
        self._session_count += 1
        self._scan_started_monotonic = now
        self._last_packet_monotonic = now
        self._last_heartbeat_log_monotonic = now

        logger.info(
            f"BLEScanner: active scan started (session={self._session_count}, restarts={self._restart_count})"
        )

    async def _run(self):
        while True:
            try:
                await self._open_transport()

                while True:
                    await asyncio.sleep(self.HEALTH_CHECK_INTERVAL_SEC)

                    now = time.monotonic()

                    # Periodic low-noise health heartbeat
                    if self._last_packet_monotonic > 0:
                        since_last_packet = now - self._last_packet_monotonic
                        since_last_heartbeat = now - self._last_heartbeat_log_monotonic

                        if since_last_heartbeat >= self.HEARTBEAT_LOG_INTERVAL_SEC:
                            uptime = now - self._scan_started_monotonic
                            logger.debug(
                                "BLEScanner: heartbeat healthy "
                                f"(session={self._session_count}, restarts={self._restart_count}, "
                                f"uptime={uptime:.0f}s, last_packet_age={since_last_packet:.0f}s, "
                                f"handlers={len(self.handlers)})"
                            )
                            self._last_heartbeat_log_monotonic = now

                        # Detect stalled scanning path and force a reconnect.
                        # In your environment there should be ongoing BLE traffic,
                        # so prolonged silence indicates a stuck scanner/transport.
                        if since_last_packet >= self.INACTIVITY_TIMEOUT_SEC:
                            logger.warning(
                                "BLEScanner: no BLE packets received for "
                                f"{since_last_packet:.0f}s; restarting scanner "
                                f"(session={self._session_count}, restarts={self._restart_count})"
                            )
                            break

            except asyncio.CancelledError:
                logger.info("BLEScanner: supervisor task cancellation requested")
                raise
            except Exception as e:
                logger.error(f"BLEScanner: scanner loop error: {e}", exc_info=True)
            finally:
                await self._shutdown()

            self._restart_count += 1
            logger.warning(
                f"BLEScanner: reconnecting in {self.RECONNECT_DELAY_SEC}s "
                f"(next_restart_count={self._restart_count})"
            )
            await asyncio.sleep(self.RECONNECT_DELAY_SEC)
