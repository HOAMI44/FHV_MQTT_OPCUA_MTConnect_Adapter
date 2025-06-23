import subprocess
import sys
import os
import time
from paho.mqtt import client as mqtt_client
import json
import socket
import threading
from flask import Flask, Response
import html

app = Flask(__name__)

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def start_mosquitto():
    if getattr(sys, 'frozen', False):
        # Running as a exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        # Running as a script
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    mosquitto_path = os.path.join(exe_dir, "mosquitto", "mosquitto.exe")
    print("EXE-Ordner:", exe_dir)
    print("Gesuchter Mosquitto Pfad:", mosquitto_path)
    
    try:
        # Start mosquitto broker
        broker_process = subprocess.Popen([mosquitto_path, "-v"], 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
        print("Mosquitto erfolgreich gestartet")
        return broker_process
    except Exception as e:
        print(f"Mosquitto broker konnte nicht gestartet werden: {e}")
        sys.exit(1)

# MQTT Client Setup
client_id = f'python-mqtt-{time.time()}'
mqtt_client = mqtt_client.Client(client_id)

monitored_variables = [
    "ACTUAL_CURRENT", "ACTUAL_VOLTAGE", "ACTUAL_POWER", "ACTUAL_WELDINGTIME", "ACTUAL_GASFLOW",
    "ACTUAL_WFS", "DISPLAY_CURRENT", "DISPLAY_ENERGY", "DISPLAY_POWER",
    "DISPLAY_STATUS", "DISPLAY_VOLTAGE", "DISPLAY_WFS", "WIREBUFFER_VALUE",
    "ARCSTABLE", "ARC_LENGTH_STABILIZER_STATUS", "CURRENTFLOW", "ERROR",
    "PENETRATION_STABILIZER_STATUS", "PROCESS_ACTIVE", "PROCESS_MAINPHASE",
    "SAFETY_STATUS", "WIREEND_VALUE", "WIREEND_VALUE_DRUM", "WIREEND_VALUE_RINGSENSOR",
    "ARCLENGTH_CORRECTION", "ARC_LENGTH_STABILIZER", "CURRENT_RECOMMVALUE",
    "END_ARCLENGTH_CORRECTION", "END_CURRENT", "END_CURRENT_TIME", "GASFACTOR",
    "GASPOSTFLOW", "GASPREFLOW", "GASVALUE", "PENETRATION_STABILIZER",
    "PULSDYNAMIC_CORRECTION", "SFI", "SFI_HOTSTART", "SLOPE_1", "SLOPE_2",
    "START_ARCLENGTH_CORRECTION", "START_CURRENT", "START_CURRENT_TIME",
    "SYNCHROPULSE_ARCLENGTH_CORR_HIGH", "SYNCHROPULSE_ARCLENGTH_CORR_LOW",
    "SYNCHROPULSE_DELTA_FEEDER", "SYNCHROPULSE_DUTYCYCLE", "SYNCHROPULSE_ENABLE",
    "SYNCHROPULSE_FREQUENCY", "TRIGGER_MODE", "VOLTAGE_RECOMMVALUE",
    "WELDING_MODE", "WFS_COMMANDVALUE",
    "JOBMODE", "JOBNAME", "JOBNUMBER", "JOBREVISION", "JOBSLOPE"
]

latest_values = {}
sequence = 1

def on_connect(client, userdata, flags, rc):
    print("on_connect called with rc =", rc)
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe("FRONIUS/welding/data/#")
        print("Subscribed to: FRONIUS/welding/data/#")
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    print(f"Received on topic: {msg.topic}")
    print(f"Payload: {msg.payload}")
    # Extrahiere den Variablennamen aus dem Topic
    variable = msg.topic.split("/")[-1]
    if variable in monitored_variables:
        latest_values[variable] = html.escape(msg.payload.decode())

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

@app.route("/probe")
def probe():
    data_items = ""
    for key in latest_values:
        category = "SAMPLE" if "STATUS" not in key else "EVENT"
        dtype = "STRING"
        units = ""
        native_units = ""
        
        if "CURRENT" in key:
            dtype = "AMPERAGE"
            units = ' units="AMPERE"'
            native_units = ' nativeUnits="AMPERE"'
        elif "VOLTAGE" in key:
            dtype = "VOLTAGE"
            units = ' units="VOLT"'
            native_units = ' nativeUnits="VOLT"'
        elif "TEMP" in key or "TEMPERATURE" in key:
            dtype = "TEMPERATURE"
            units = ' units="CELSIUS"'
            native_units = ' nativeUnits="CELSIUS"'
        elif "POWER" in key:
            dtype = "POWER"
            units = ' units="WATT"'
            native_units = ' nativeUnits="WATT"'
        elif "TIME" in key:
            dtype = "ACCUMULATED_TIME"
            units = ' units="SECOND"'
            native_units = ' nativeUnits="SECOND"'
        elif "STATUS" in key:
            dtype = "AVAILABILITY"
        elif "GAS" in key:
            dtype = "FLOW"
            units = ' units="LITER/MINUTE"'
            native_units = ' nativeUnits="LITER/MINUTE"'
        elif "WFS" in key:
            dtype = "VELOCITY"
            units = ' units="MILLIMETER/SECOND"'
            native_units = ' nativeUnits="MILLIMETER/SECOND"'

        data_items += f'<DataItem category="{category}" id="{key}" name="{key}" type="{dtype}"{units}{native_units} />\n'

    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<MTConnectDevices xmlns:mt="urn:mtconnect.org:MTConnectDevices:1.3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="urn:mtconnect.org:MTConnectDevices:1.3" xsi:schemaLocation="urn:mtconnect.org:MTConnectDevices:1.3 ./schemas/Spec1_3/MTConnectDevices_1.3.xsd">
  <Header creationTime="{time.strftime('%Y-%m-%dT%H:%M:%SZ')}" assetBufferSize="1024" sender="WeldingAdapter" assetCount="0" version="1.3" instanceId="1" bufferSize="131072" />
  <Devices>
    <Device uuid="WELDING.001" name="WELDING" id="WELDING.001">
      <Description model="WELDING" manufacturer="WELDING" serialNumber="001">Welding MTConnect Adapter</Description>
      <DataItems>
        <DataItem category="EVENT" id="Wavail" type="AVAILABILITY" name="avail" />
        <DataItem id="Wfmode" name="fmode" category="EVENT" type="FUNCTIONAL_MODE" />
      </DataItems>
      <Components>
        <Welding id="WeldingSystem" name="WeldingSystem">
          <DataItems>
            {data_items}
          </DataItems>
        </Welding>
        <Controller name="Controller" id="Wct1">
          <DataItems>
            <DataItem type="EMERGENCY_STOP" name="estop" category="EVENT" id="Westop" />
            <DataItem type="SYSTEM" category="CONDITION" id="Wsystem" name="system" />
            <DataItem type="CONTROLLER_MODE" name="pmode" category="EVENT" id="Wpmode" />
            <DataItem type="PROGRAM" name="pprogram" category="EVENT" id="Wpprogram" />
            <DataItem type="EXECUTION" name="pexecution" category="EVENT" id="Wpexecution" />
            <DataItem type="PATH_FEEDRATE_OVERRIDE" subType="PROGRAMMED" name="pFovr" category="EVENT" units="PERCENT" nativeUnits="PERCENT" id="WpFovr" />
          </DataItems>
        </Controller>
        <Systems id="WSystems1" name="Systems1">
          <Components>
            <Electric id="WElectricSystem1" name="ElectricSystem1">
              <DataItems>
                <DataItem category="CONDITION" id="WElectricSystem1_cond" name="ElectricSystem1_cond" type="SYSTEM" />
              </DataItems>
            </Electric>
            <Pneumatic id="WPneumaticSystem1" name="PneumaticSystem1">
              <DataItems>
                <DataItem category="CONDITION" id="WPneumaticSystem1_cond" name="PneumaticSystem1_cond" type="SYSTEM" />
              </DataItems>
            </Pneumatic>
          </Components>
        </Systems>
      </Components>
    </Device>
  </Devices>
</MTConnectDevices>'''
    return Response(xml, mimetype='application/xml')

@app.route("/current")
def current():
    global sequence
    timestamp = time.strftime('%Y-%m-%dT%H:%M:%S')
    samples = ""
    events = ""

    for key, value in latest_values.items():
        tag = "SAMPLE"
        mt_type = "VALUE"
        if "STATUS" in key:
            tag = "EVENT"
            mt_type = "AVAILABILITY"
        elif "CURRENT" in key:
            mt_type = "AMPERAGE"
        elif "VOLTAGE" in key:
            mt_type = "VOLTAGE"
        elif "TEMP" in key or "TEMPERATURE" in key:
            mt_type = "TEMPERATURE"
        elif "POWER" in key:
            mt_type = "POWER"

        entry = f'<{mt_type} dataItemId="{key}" timestamp="{timestamp}" name="{key}" sequence="{sequence}">{value}</{mt_type}>\n'

        if tag == "EVENT":
            events += entry
        else:
            samples += entry

        sequence += 1

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<MTConnectStreams xmlns="urn:mtconnect.org:MTConnectStreams:1.3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header creationTime="{timestamp}" sender="WeldingAdapter" instanceId="1" bufferSize="130000" version="1.3" nextSequence="{sequence}" firstSequence="1" lastSequence="{sequence-1}" />
  <Streams>
    <DeviceStream name="WeldingMachine" uuid="welding-001">
      <ComponentStream component="WELDING" name="Main" componentId="c1">
        <Samples>
          {samples}
        </Samples>
        <Events>
          {events}
        </Events>
      </ComponentStream>
    </DeviceStream>
  </Streams>
</MTConnectStreams>'''
    return Response(xml, mimetype='application/xml')

@app.route("/sample")
def sample():
    return current()

def main():
    # Start Mosquitto broker
    broker_process = start_mosquitto()
    
    try:
        # Get welding machine IP
        default_ip = get_local_ip()
        welding_ip = input(f"Enter welding machine IP (default={default_ip}): ") or default_ip
        mqtt_port = "1883"  # Default MQTT port
        
        print(f"\nConnecting to welding machine at {welding_ip}:{mqtt_port}")
        print("Starting MTConnect adapter...")
        
        # Connect to MQTT broker
        try:
            mqtt_client.connect(welding_ip, int(mqtt_port))
            mqtt_client.subscribe("FRONIUS/welding/data/#")
            mqtt_client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            return
        
        # Start Flask server
        print("\nMTConnect adapter is running!")
        print("You can access the following endpoints:")
        print(f"  - http://localhost:5050/probe")
        print(f"  - http://localhost:5050/current")
        print(f"  - http://localhost:5050/sample")
        
        # Subscribe to all relevant topics
        mqtt_client.on_connect = on_connect
        mqtt_client.on_message = on_message
        # Subscribe to all subtopics under FRONIUS/welding/data
        mqtt_client.connect(welding_ip, int(mqtt_port))
        mqtt_client.subscribe("FRONIUS/welding/data/#")
        mqtt_client.loop_start()
        
        app.run(host='0.0.0.0', port=5050)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        # Cleanup
        broker_process.terminate()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == '__main__':
    main() 