About
=====

TFDeux is a fermentation control system for homebrewing.  It has been tested on Raspberry Pi but may work on other systems. It is intended to be used with a Tilt Hydrometer. 

You can use it to:
+ Monitor external temperature in your fermenter using the W1Sensor plugin.
+ Monitor the beer temperature, gravity, ABV and attenuation using the Tilt Hydrometer.
+ Turn heating and cooling on and off using the TPLinkActor (WiFi controlled socket).
+ Maintain a stable temperature in your fermentation by controlling heating and cooling based on temperature.
+ Control and monitor your fermentation process through a web frontend.

TFDeux is a fork of TFBrew, original written by Hrafnkell Eiríksson.  TFBrew supports both the brewing and fermentation process.  The original is no longer maintained, but can be made to run on current RPi platforms.  However, some underlying packages are problematic and/or deprecated with Raspberry Pi OS Bookworm.  TFDeux also includes changes made to TFBrew by Michaël Cadilhac.

TFDeux has been migrated to uses:

=======
TFDeux is a fork of TFBrew, original written by Hrafnkell Eiríksson.  TFBrew supports both the brewing and fermentation process.  The original is no longer maintained, but can be made to run on current RPi platforms.  However, some underlying packages are problematic and/or deprecated with Raspberry Pi OS Bookworm.  TFDeux has been migrated to uses:

+ aioblescan 0.2.14
+ rpi-lgpio 0.6
+ vue 3.5.13
+ quasar 2.17.4
+ echarts 5.5.1
+ blynk 2.0

TFDeux is Copyright from 2024 by Chuck Glover and is licensed by the GNU GPL v3 license.
See the LICENSE file.

TFBrew is Copyright from 2017 by Hrafnkell Eiríksson and is licensed by the GNU GPL v3 license.

Please consult the [Wiki](https://github.com/hrafnkelle/tfbrew/wiki) for further information on TFBrew.

Plugins
=======
Like TFBrew, TFDeux is based on components that send each other messages. Components are implemented via plugins and assigned to controllers (Fridge and Heater).
The following components have been tested:

+ TiltSensor - for using the Tilt Hydrometer.
+ W1Sensor - for using a ds18b20 one-wire sensors.
+ TPLinkActor - for controlling a TPLink WiFi socket.
+ HysteresisLogic - for on/off temperature control with a hysteresis (e.g. fermentation fridge control).
+ DummyActor - simulating an actor, just prints out the actions.
+ DummySensor - simulating a sensor with a configurable value + noise.
+ BlynkLib - for communicating with a Blynk frontend (sadly this is very expensive now for our use but it does work).

The following components have NOT been tested, but worked under TFBrew:

+ RTDSensor - for using PT100 sensors through the MAX31865.
+ iSpindelSensor - for using the iSpindel Hydrometer.
+ GPIOActor - for controlling relays (SSR) with the GPIO pins on the Raspberry Pi.
+ SimpleWebView - for viewing the state of sensors, actors, etc in a web browser.
+ PIDLogic - for precise temperature control with a PID (e.g. recirculated mash).
+ Ubidots - for logging to the Ubidots IoT cloud.

Configuration
=============

Configuration is handled through the YAML configuration file (config.yaml). TFDeux was developed and tested using the included configuration. The configuration for a Fermenter in a repurposed refrigerator with a heating element added. The configuration file addresses:

+ Logging levels to console and log file.
+ Sensors for reading temperatures and/or gravity.
+ Actors like wifi sockets for controlling cooling and heating.
+ Controllers to which the sensors and actors are assigned along with the logic used.
+ Extensions for web and/or Blynk.
+ Connections which route messages from sending to receiving endpoint. For example:
        ```
        Cooling.power => web.coolingpower (Sends Cooling power state to the web UI)
        ```

Installation
============
TFDeux requires at least Python 3.11 (for asyncio async/await support)

Clone this repository, and set up a virtualenv
pip install the python packages in the requirements.txt file into your virtualenv
```
git clone https://github.com/ChuckGl/tfdeux.git
cd tfdeux
git checkout tfdeux

# Setup python virtual environment. Required for Bookworm.  See link for more: https://www.raspberrypi.com/documentation/computers/os.html#python-on-raspberry-pi
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Setup permissions for aioblescan to get TILT data via BLE.
sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/python3.11

```

then run the `python tfdeux.py` file

Please consult the [Wiki](https://github.com/ChuckGl/tfdeux/wiki) for further information.

