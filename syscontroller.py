# syscontroller.py

import os
import subprocess
import logging

logger = logging.getLogger("syscontroller")

def reboot():
    logger.warning("System: Reboot command issued")
    os.system("sudo shutdown -r ")

def poweroff():
    logger.warning("System: Poweroff command issued")
    os.system("sudo shutdown -P ")

def restart_service():
    logger.warning("System: Restarting tfdeux service")
    os.system("sudo systemctl restart tfdeux.service")

def stop_service():
    logger.warning("System: Stopping tfdeux service")
    os.system("sudo systemctl stop tfdeux.service")

def usbreset(vendor_id="04b4", product_id="fd15"):
    logger.warning(f"Attempting USB reset for device {vendor_id}:{product_id}")
    try:
        result = subprocess.run(['lsusb'], stdout=subprocess.PIPE, check=True)
        for line in result.stdout.decode().splitlines():
            if f"{vendor_id}:{product_id}" in line:
                parts = line.split()
                bus = parts[1]
                device = parts[3].rstrip(':')
                devpath = f"/dev/bus/usb/{bus}/{device}"
                logger.info(f"Resetting USB device at {devpath}")
                os.system(f"sudo usbreset {devpath}")
                return True
        logger.error("Device not found in lsusb output")
    except Exception as e:
        logger.error(f"USB reset failed: {e}")
    return False

def handle_system_command(endpoint, data, controller_name="System"):
    if endpoint == "admin":
        if data == "reboot":
            logger.info(f"{controller_name}: Reboot command received.")
            reboot()
        elif data == "restartsvc":
            logger.info(f"{controller_name}: Restart service command received.")
            restart_service()
        elif data == "stopsvc":
            logger.info(f"{controller_name}: Stop service command received.")
            stop_service()
        elif data == "poweroff":
            logger.info(f"{controller_name}: Poweroff command received.")
            poweroff()
        else:
            logger.warning(f"{controller_name}: Unknown admin command received: {data}")
    else:
        logger.warning(f"{controller_name}: Unhandled endpoint {endpoint} with data {data}")

