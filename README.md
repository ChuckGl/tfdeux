About
=====

TFDeux is a fermentation control system for homebrewing.  It has been tested on Raspberry Pi but may work on other systems. It is intended to be used with a Tilt Hydrometer. 

You can use it to:
+ Monitor external temperature in your fermenter using the W1Sensor plugin.
+ Monitor the beer temperature, gravity, ABV and attenuation using the Tilt Hydrometer.
+ Turn heating and cooling on and off using the TPLinkActor (WiFi controlled socket) or the GPIOActor (raspberry pi).
+ Maintain a stable temperature in your fermentation by combining a heater and temperature sensor in a controller
  with process logic.
+ Control and monitor your fermentation process through a web frontend.

TFDeux is a fork of TFBrew, original written by Hrafnkell Eiríksson. TFBrew supports both the brewing and fermentation process.  The original is no longer supported, but can be made to run on current RPi platforms.

TFBrew is Copyright from 2024 by Chuck Glover and is licensed by the GNU GPL v3 license.
See the LICENSE file.

TFBrew is Copyright from 2017 by Hrafnkell Eiríksson and is licensed by the GNU GPL v3 license.

Please consult the [Wiki](https://github.com/hrafnkelle/tfbrew/wiki) for further information on TFBrew.

Plugins
=======
Like TFBrew, TFDeux is based on components that send each other messages. Components are implemented via plugins and assigned to controllers (Fridge and Heater).
The following components have been tested:

+ TiltSensor - for using the Tilt Hydrometer
+ W1Sensor - for using one-wire sensors like the ds18b20
+ TPLinkActor - for controlling a TPLink WiFi socket
+ HysteresisLogic - for on/off temperature control with a hysteresis (e.g. fermentation fridge control)
+ DummyActor - simulating an actor, just prints out the actions
+ DummySensor - simulating a sensor with a configurable value + noise
+ BlynkLib - for communicating with a Blynk frontend

The following components have NOT been tested, but worked under TFBrew
+ RTDSensor - for using PT100 sensors through the MAX31865
+ iSpindelSensor - for using the iSpindel Hydrometer
+ GPIOActor - for controlling relays (SSR) with the GPIO pins on the Raspberry Pi
+ SimpleWebView - for viewing the state of sensors, actors, etc in a web browser
+ PIDLogic - for precise temperature control with a PID (e.g. recirculated mash)
+ Ubidots - for logging to the Ubidots IoT cloud

Configuration
=============

It is configured throug a YAML configuration file, found in config.yaml.
The included configuration might work for a single vessel BIAB system controlled by a Raspberry Pi,
using GPIO for actors and a one-wire (w1) ds18b20 (or similar) temperature sensor.
This could be controlled by a Blynk user interface.
See the included config.yaml as an example.

First, actors and sensors are declared.
Then, one or more controller is declared, a logic (how do decide when to activate e.g. heater), a sensor and an actor are attached.
Extensions can then be loaded.
Finally, message routing is set up in connections.
Each component has one or more sending and receving endpoint.
Messages from one component to another are set up like
```
KettleController.power=>UserInterface.powerdisplay
```
Installation
============
TFBrew (tfmod2) requires at least Python 3.11 (for asyncio async/await support)

Clone this repository, and set up a virtualenv
pip install the python packages in the requirements.txt file into your virtualenv
```
git clone https://github.com/ChuckGl/tfbrew.git
cd tfbrew
git checkout tfmod2

# Setup python virtual environment. Required for Bookworm.  See link for more: https://www.raspberrypi.com/documentation/computers/os.html#python-on-raspberry-pi
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# Link virtual environment to system-level lgpio package. The lgpio package in combination with rpi-lgpio replaces RPi.GPIO in bookworm. The lgpio package is managed using apt which is not supported in virtual environments. This gets around that issue for now.
ln -s /usr/lib/python3/dist-packages/lgpio.py $VIRTUAL_ENV/lib/python3.11/site-packages/lgpio.py
ln -s /usr/lib/python3/dist-packages/lgpio-0.2.2.0.egg-info $VIRTUAL_ENV/lib/python3.11/site-packages/lgpio-0.2.2.0.egg-info
ln -s /usr/lib/python3/dist-packages/_lgpio.cpython-311-aarch64-linux-gnu.so $VIRTUAL_ENV/lib/python3.11/site-packages/_lgpio.cpython-311-aarch64-linux-gnu.so

```

then run the tfbrew.py file

Please consult the [Wiki](https://github.com/hrafnkelle/tfbrew/wiki) for further information.
