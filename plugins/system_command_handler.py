import os
import logging
import event

logger = logging.getLogger(__name__)

def handle_system_command(endpoint, data, controller_name="System"):
    if endpoint == "admin":
        if data == "reboot":
            logger.info(f"{controller_name}: Reboot command received.")
            os.system('sudo shutdown -r')
            event.notify(event.Event(source=controller_name, endpoint='admin', data='rebooting'))
        elif data == "poweroff":
            logger.info(f"{controller_name}: Poweroff command received.")
            os.system('sudo shutdown -P')
            event.notify(event.Event(source=controller_name, endpoint='admin', data='powering_off'))
        else:
            logger.warning(f"{controller_name}: Unknown command received: {data}")
    else:
        logger.warning(f"{controller_name}: Unhandled endpoint {endpoint} with data {data}")

