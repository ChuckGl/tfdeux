import os
import logging
import event

logger = logging.getLogger(__name__)

def handle_system_command(endpoint, data, controller_name="System"):
    if endpoint == "admin":
        if data == "reboot":
            logger.info(f"{controller_name}: Reboot command received.")
            os.system('sudo shutdown -r')
        elif data == "restartsvc":
            logger.info("System: Restart service command received.")
            os.system('sudo service tfdeux restart')
        elif data == "stopsvc":
            logger.info("System: Stop service command received.")
            os.system('sudo service tfdeux stop')
        elif data == "poweroff":
            logger.info(f"{controller_name}: Poweroff command received.")
            os.system('sudo shutdown -P')
        else:
            logger.warning(f"{controller_name}: Unknown command received: {data}")
    else:
        logger.warning(f"{controller_name}: Unhandled endpoint {endpoint} with data {data}")

