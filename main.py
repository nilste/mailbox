import machine # Used for deepsleep
import time # Used for sleep
import json # Used for config file
import system # Used for voltage
from machine import Pin
from dht import DHT

resetReason = machine.reset_cause()
wakeReason = machine.wake_reason()[0] # (wake_reason, gpio_list)

### SETTINGS ###
pycom.rgbled(0xFFFF00) # Yellow

# Sensor used for measuring temperature
# DHT11: 0, DHT22: 1
DHTType = 1
DHTPin = 'P23'

# Reed switch used to wake the device
reedPin = 'P22'

# Internal voltage divider used for measuring battery voltage
# These values are from Pycom Extension Board v3.1
batteryPin = 'P16'
resistorR1 = 1000
resistorR2 = 1000
batteryAttn = 6.0

# Deep sleep settings
# Mode can be machine.WAKEUP_ALL_LOW or machine.WAKEUP_ANY_HIGH
# enable_pull decides if pull up / down resistors should be enabled during sleep
secondsToSleep = 60 * 60 * 4
wakePins = ['P22']
wakeMode = machine.WAKEUP_ANY_HIGH
wakePull = True

### NETWORK ###
with open('config.json') as file:
    config = json.load(file)

if config['USE_LORA']:
    from network import LoRa
    import socket
    import ubinascii
    import struct

    # Initialise LoRa in LORAWAN mode.
    lora = LoRa(mode=LoRa.LORAWAN, region=LoRa.EU868)

    if resetReason == machine.DEEPSLEEP_RESET:
        print('Woke from deepsleep...')
        lora.nvram_restore()
    else:
        print('Connecting to LoRa...')
        app_eui = ubinascii.unhexlify(config['APP_EUI'])
        app_key = ubinascii.unhexlify(config['APP_KEY'])

        lora.join(activation=LoRa.OTAA, auth=(app_eui, app_key), timeout=0)
        while not lora.has_joined():
            print('Not yet joined...')
            pycom.rgbled(0xcc00ff)
            time.sleep(1)
            pycom.rgbled(0x000000)
            time.sleep(0.5)

        print("Joined network")
    
    # Create a LoRa socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

    # Set the LoRaWAN data rate
    s.setsockopt(socket.SOL_LORA, socket.SO_DR, 5)

elif config['USE_WIFI']:
    print('Connecting to WiFi...')
    from network import WLAN
    import urequests as requests
    try:
        wlan = WLAN(mode=WLAN.STA)
        nets = wlan.scan()
        for net in nets:
            if net.ssid == config['SSID']:
                print('Network found!')
                wlan.connect(net.ssid, auth=(net.sec, config['SSID_PASS']), timeout=5000)
                while not wlan.isconnected():
                    machine.idle() # Save power while waiting
                print('WLAN connection succeeded!')
                break
    except:
        print('Was not able to connect to WiFi...')

### SENSOR SETUP ###
print('Initiating sensors...')
pycom.rgbled(0x0000FF) # Blue

dhtsensor = DHT(Pin(DHTPin, mode=Pin.OPEN_DRAIN), DHTType)
reedsensor = Pin(reedPin, mode=Pin.IN, pull=Pin.PULL_UP)
sysvolt = system.SystemVoltage(batteryPin, resistorR1, resistorR2, batteryAttn)

machine.pin_sleep_wakeup(pins=wakePins, mode=wakeMode, enable_pull=wakePull)

### SENSOR HANDLING ###
if wakeReason == machine.PIN_WAKE:
    print('Pin triggered!')
    pycom.rgbled(0xFF0000) # Red
    
    # Send notification
    if config['USE_LORA']:
        print('Sending over LoRa...')
        s.setblocking(True)
        s.bind(2) # Define port
        s.send(bytes([0x01]))
        s.setblocking(False)

    elif config['USE_WIFI'] and wlan.isconnected():
        print('Sending over WiFi...')
        try:
            payload = { "password": config['HTTP_PASSWORD'], "triggered": True }
            headers = { "Content-Type": "application/json" }
            res = requests.post(config['HTTP_URL'], headers = headers, json = payload)
            res.close()
        except:
            print('An error occured when trying to send data...')

    # Avoid sending multiple notifications
    while reedsensor.value():
        machine.idle() # Save power while waiting

elif wakeReason == machine.RTC_WAKE or resetReason == machine.WDT_RESET or resetReason == machine.PWRON_RESET:
    print('Sleep time ended')
    print('Fetching and sending data...')
    pycom.rgbled(0x00FF00) # Green

    # Fetch data from DHT sensor
    dhtresult = dhtsensor.read()
    while not dhtresult.is_valid():
        time.sleep(.5)
        dhtresult = dhtsensor.read()

    # Fetch values
    tempValue = dhtresult.temperature
    humiValue = dhtresult.humidity
    battValue = sysvolt.read()

    # Print values
    print('Temp: ', tempValue)
    print('RH: ', humiValue)
    print('Volt: ', battValue)

    # Send values
    if config['USE_LORA']:
        print('Sending over LoRa...')
        s.setblocking(True)
        s.bind(1) # Define port
        # Multiply with 100 to avoid having to send floats
        payload = struct.pack('>h', int(tempValue * 100))
        payload += struct.pack('>H', int(humiValue * 100))
        payload += struct.pack('>H', int(battValue * 100))
        s.send(payload)
        s.setblocking(False)

    elif config['USE_WIFI'] and wlan.isconnected():
        print('Sending over WiFi...')
        try:
            payload = { "password": config['HTTP_PASSWORD'], "temperature": tempValue, "humidity": humiValue, "voltage": battValue }
            headers = { "Content-Type": "application/json" }
            res = requests.post(config['HTTP_URL'], headers = headers, json = payload)
            res.close()
        except:
            print('An error occured when trying to send data...')

### GO TO SLEEP ###
print('Preparing deepsleep...')
pycom.rgbled(0x000000) # Turn off

if (config['USE_LORA']):
    lora.nvram_save()
elif config['USE_WIFI']:
    wlan.deinit() # Avoid getting wifi timeout next cycle

sleepInterval = 0
remainingSleepTime = machine.remaining_sleep_time() # Milliseconds
if (remainingSleepTime > 0):
    sleepInterval = remainingSleepTime
else:
    sleepInterval = int(secondsToSleep * 1000)

machine.deepsleep(sleepInterval)