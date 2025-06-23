from opcua import Client
from flask import Flask, Response
import time
import threading
import socket
import html
import psutil
import os
import datetime
from collections import deque

app = Flask(__name__)

# Performance monitoring variables
variable_timestamps = {}
variable_count = 0
update_times = deque(maxlen=100)  # Store last 100 update times for rate calculation
last_update_time = time.time()
performance_metrics = {
    "delay_ms": 0,
    "update_rate": 0,
    "memory_mb": 0,
    "cpu_percent": 0,
    "last_updated": time.time()
}

# Lokale IP-Adresse automatisch erkennen
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

# Verbindung konfigurieren
default_ip = get_local_ip()
opcua_ip = input(f"OPC UA Server IP (default={default_ip}): ") or default_ip
opcua_port = input("OPC UA Server Port (default=4840): ") or "4840"
endpoint = f"opc.tcp://{opcua_ip}:{opcua_port}"
print(f"Connecting to: {endpoint}")

client = Client(endpoint)
client.connect()

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

def browse_and_find_variables():
    found = {}
    objects_node = client.get_objects_node()
    stack = [objects_node]

    while stack:
        node = stack.pop()
        try:
            for child in node.get_children():
                try:
                    name = child.get_browse_name().Name
                    if name in monitored_variables:
                        found[name] = child
                    stack.append(child)
                except:
                    continue
        except:
            continue
    return found

found_nodes = browse_and_find_variables()

def update_values():
    global variable_count, last_update_time, update_times
    
    while True:
        current_time = time.time()
        
        # Calculate update rate
        time_diff = current_time - last_update_time
        last_update_time = current_time
        if time_diff > 0:  # Avoid division by zero
            update_times.append(time_diff)
        
        for key, node in found_nodes.items():
            try:
                value = str(node.get_value())
                latest_values[key] = html.escape(value)
                
                # Store timestamp for this variable
                variable_timestamps[key] = current_time
                variable_count += 1
            except:
                continue
                
        time.sleep(1)

def update_performance_metrics():
    """Update performance metrics periodically"""
    while True:
        try:
            process = psutil.Process(os.getpid())
            
            # CPU usage
            performance_metrics["cpu_percent"] = process.cpu_percent(interval=1.0)
            
            # Memory usage in MB
            memory_info = process.memory_info()
            performance_metrics["memory_mb"] = memory_info.rss / (1024 * 1024)
            
            # Update rate calculation (updates per second)
            if update_times:
                avg_time_between_updates = sum(update_times) / len(update_times)
                if avg_time_between_updates > 0:
                    performance_metrics["update_rate"] = 1.0 / avg_time_between_updates
                else:
                    performance_metrics["update_rate"] = 0
            else:
                performance_metrics["update_rate"] = 0
                
            # Calculate average delay between data updates and HTTP response
            current_time = time.time()
            total_delay = 0
            count = 0
            
            for key, timestamp in variable_timestamps.items():
                delay_ms = (current_time - timestamp) * 1000  # Convert to ms
                total_delay += delay_ms
                count += 1
                
            # Update average delay
            if count > 0:
                performance_metrics["delay_ms"] = total_delay / count
                
            # Update timestamp
            performance_metrics["last_updated"] = time.time()
            
            # Clear console on Windows
            if os.name == 'nt':
                os.system('cls')
            else:
                os.system('clear')  # For Linux/Mac
                
            # Print performance metrics to console with prettier formatting
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            print("\n" + "="*50)
            print(f"  OPC UA-MTConnect ADAPTER PERFORMANCE ({current_time})")
            print("="*50)
            print(f"Verzögerung:         {performance_metrics['delay_ms']:.2f} ms")
            print(f"Abfragerate:         {performance_metrics['update_rate']:.2f} Updates/Sek")
            print(f"Speicherverbrauch:   {performance_metrics['memory_mb']:.2f} MB")
            print(f"CPU-Auslastung:      {performance_metrics['cpu_percent']:.2f}%")
            print("-"*50)
            print(f"Empfangene Updates:    {variable_count}")
            print(f"Überwachte Variablen:  {len(latest_values)}")
            print("="*50)
            print("\nDrücke CTRL+C zum Beenden...")
            
            time.sleep(3)  # Update every 3 seconds to avoid console spam
        except Exception as e:
            print(f"Error updating performance metrics: {e}")
            time.sleep(1)

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

    # Add performance metrics as DataItems
    data_items += '<DataItem category="SAMPLE" id="DELAY_MS" name="DELAY_MS" type="PROCESS_TIME" units="MILLISECOND" nativeUnits="MILLISECOND" />\n'
    data_items += '<DataItem category="SAMPLE" id="UPDATE_RATE" name="UPDATE_RATE" type="PROCESS_TIMER" units="COUNT/SECOND" nativeUnits="COUNT/SECOND" />\n'
    data_items += '<DataItem category="SAMPLE" id="MEMORY_MB" name="MEMORY_MB" type="PROCESS_METRIC" units="MEGABYTE" nativeUnits="MEGABYTE" />\n'
    data_items += '<DataItem category="SAMPLE" id="CPU_PERCENT" name="CPU_PERCENT" type="PROCESS_METRIC" units="PERCENT" nativeUnits="PERCENT" />\n'

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

        entry = f'<{mt_type} dataItemId="{key}" timestamp="{timestamp}"name="{key}" sequence="{sequence}">{value}</{mt_type}>\n'

        if tag == "EVENT":
            events += entry
        else:
            samples += entry

        sequence += 1

    # Add performance metrics to samples
    samples += f'<VALUE dataItemId="DELAY_MS" timestamp="{timestamp}" name="DELAY_MS" sequence="{sequence}">{performance_metrics["delay_ms"]:.2f}</VALUE>\n'
    sequence += 1
    samples += f'<VALUE dataItemId="UPDATE_RATE" timestamp="{timestamp}" name="UPDATE_RATE" sequence="{sequence}">{performance_metrics["update_rate"]:.2f}</VALUE>\n'
    sequence += 1
    samples += f'<VALUE dataItemId="MEMORY_MB" timestamp="{timestamp}" name="MEMORY_MB" sequence="{sequence}">{performance_metrics["memory_mb"]:.2f}</VALUE>\n'
    sequence += 1
    samples += f'<VALUE dataItemId="CPU_PERCENT" timestamp="{timestamp}" name="CPU_PERCENT" sequence="{sequence}">{performance_metrics["cpu_percent"]:.2f}</VALUE>\n'
    sequence += 1

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<MTConnectStreams xmlns="urn:mtconnect.org:MTConnectStreams:1.3" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Header creationTime="{timestamp}" sender="WeldingAdapter" instanceId="1" bufferSize="130000" version="1.3"
  nextSequence="{sequence}" firstSequence="1" lastSequence="{sequence-1}" />
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

@app.route("/metrics")
def metrics():
    """Endpoint to display performance metrics"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>OPC UA-MTConnect Adapter Metriken</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .metric {{ margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }}
            .metric h3 {{ margin-top: 0; color: #333; }}
            .value {{ font-size: 24px; font-weight: bold; color: #0066cc; }}
            .label {{ color: #666; }}
            .update-time {{ font-size: 12px; color: #999; margin-top: 10px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .header {{ background-color: #f5f5f5; padding: 10px; margin-bottom: 20px; border-radius: 5px; }}
        </style>
        <meta http-equiv="refresh" content="2">
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>OPC UA-MTConnect Adapter Leistungsmetriken</h1>
                <p>Echtzeit-Überwachung der Adapter-Leistung</p>
            </div>
            
            <div class="metric">
                <h3>Verzögerung (OPC UA → HTTP)</h3>
                <div class="value">{performance_metrics["delay_ms"]:.2f} ms</div>
                <div class="label">Durchschnittliche Verzögerung zwischen Datenempfang und HTTP-Verfügbarkeit</div>
            </div>
            
            <div class="metric">
                <h3>Abfragerate</h3>
                <div class="value">{performance_metrics["update_rate"]:.2f} Updates/Sekunde</div>
                <div class="label">Durchschnittliche Anzahl der OPC UA Abfragen pro Sekunde</div>
            </div>
            
            <div class="metric">
                <h3>Speicherverbrauch</h3>
                <div class="value">{performance_metrics["memory_mb"]:.2f} MB</div>
                <div class="label">Aktueller Arbeitsspeicherverbrauch des Prozesses</div>
            </div>
            
            <div class="metric">
                <h3>CPU-Auslastung</h3>
                <div class="value">{performance_metrics["cpu_percent"]:.2f}%</div>
                <div class="label">Aktuelle CPU-Auslastung des Prozesses</div>
            </div>
            
            <div class="update-time">
                Letzte Aktualisierung: {datetime.datetime.fromtimestamp(performance_metrics["last_updated"]).strftime('%H:%M:%S')}
            </div>
            
            <div class="header">
                <p>Insgesamt empfangene Updates: {variable_count}</p>
                <p>Überwachte Variablen: {len(latest_values)}</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    print("\nStarting performance monitoring...")
    perf_thread = threading.Thread(target=update_performance_metrics, daemon=True)
    perf_thread.start()
    print("Performance monitoring activated. Console will update every 3 seconds.")
    
    print("\nStarting OPC UA data update thread...")
    threading.Thread(target=update_values, daemon=True).start()
    
    print("\nMTConnect adapter is running!")
    print("You can access the following endpoints:")
    print(f"  - http://localhost:5050/probe")
    print(f"  - http://localhost:5050/current")
    print(f"  - http://localhost:5050/sample")
    print(f"  - http://localhost:5050/metrics")
    
    app.run(host='0.0.0.0', port=5050)
