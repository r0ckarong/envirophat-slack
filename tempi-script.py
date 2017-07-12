import time
import math
import vcgencmd
import os
import json
import requests
import pyowm
import schedule

from datetime import datetime
from envirophat import light, weather, leds

# Declaring global variables
temp = 0
tempmed = 0
temp_calibrated = 0
cpu_temp = 0
outside_temp = 0
outside_location = ""
outside_condition = ""
currtime = datetime.now().strftime('%H:%M:%S')

# Slack Webhook stored in filesystem
slack_webhook = os.environ["SLACK_WEBHOOK"]

# Data for Openweathermap Query
owm_key = os.environ["OWM_KEY"]
owm = pyowm.OWM(owm_key)

zip_code = "60433"
country_code = "de"
unit = "celsius"

# Sensor offset factor
factor = 0.868218182

# Open log file for temp data
out = open('enviro.log', 'w')
out.write('Time\tTemp (Sensor)\tTemp (Calibrated)\tTemp (Rounded)\tCPU Temp\n')

def get_condition():
    """TODO

    Reads current condition and maps emoji and icons to the message which is to be sent to Slack.
    """
    get_detailed_status()
    get_weather_code()

def get_outside():
    """Polls the weather data from openweathermap API and returns values for global usage.
    """
    global outside_temp
    global outside_condition
    global outside_location

    observation = owm.weather_at_zip_code(zip_code,country_code)
    w = observation.get_weather()
    outside_temp = w.get_temperature(unit)['temp']
    outside_condition = w.get_detailed_status().title().encode()

def get_temps():
    """Get measured temperatures from envirophat and raspberry pi CPU sensor.
    Calculate offset measured temp. Format for further use.
    """
    global cpu_temp
    global temp
    global tempmed
    global temp_calibrated

    cpu_temp = vcgencmd.measure_temp()

    temp = weather.temperature()
    temp_calibrated = temp - ((cpu_temp - temp)/factor)
    tempmed = '{:.1f}'.format(round(temp_calibrated, 2))

def send_message():
    """Build message string from calculated and collected values.
    Post request to Slack Webhook as JSON.
    """
    message = """It is currently %s in %s, Frankfurt am Main\nOutside there is "%s" at %s C\nInside the office we have a temperature of %s C"""

    post = message % (str(currtime), zip_code, outside_condition, str(outside_temp), str(tempmed))

    # print message

    payload = {'text':post}
    requests.post(slack_webhook, json=payload)

def write_file():
    out.write('%s\t%f\t%f\t%s\t%f\n' % (currtime, temp, temp_calibrated, tempmed, cpu_temp))

def write_json():
    """TODO

    Supposed to write JSON data structure into file. Will be used as input
    for visualization.

    Currently unfinished.
    """
    date = datetime.now().strftime('%d-%m-%Y')

    json_file = open('weather.json', 'w')
    data = {
    'temperature':tempmed,
    'outside_temp':outside_temp,
    'outside_condition':outside_condition,
    'outside_location':outside_location,
    'time':currtime,
    'date':date
    }
    datarray = []
    datarray.append(data)

    json_file.append(data)
    json.dump(dataarray, weather, indent=4)
    json_file.flush()

def perform_update():
    """Update weather data and write entries to file(s).
    """
    global currtime
    currtime = datetime.now().strftime('%H:%M:%S')
    lux = light.light()
    leds.on()
    get_outside()
    get_temps()
    write_file()
    # write_json()
    # send_message()
    out.flush()
    leds.off()

# Schedule messages
# schedule.every().day.at("08:00").do(send_message)
# schedule.every().day.at("12:00").do(send_message)
schedule.every().hour.at(":00").do(send_message)

try:
    while True:
        perform_update()

        schedule.run_pending()

        time.sleep(30)

except KeyboardInterrupt:
    leds.off()
    out.close()
    # json_file.close()
