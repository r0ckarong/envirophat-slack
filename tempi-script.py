import time
import math
import vcgencmd
import os
import json
import requests
import pyowm
import schedule
import ast
import telepot
import logging

from datetime import datetime
from envirophat import light, weather, leds
from pyowm.exceptions.api_call_error import APICallError

# Set up logging
logging.basicConfig(filename='tempi.log',level=logging.INFO)
logger = logging.getLogger(__name__)
# handler = logging.FileHandler('tempi.log')
# handler.setLevel(logging.INFO)
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)

# Bot stuff
user_id = os.environ['USER_ID']
bot = telepot.Bot(os.environ['BOT_TOKEN'])

# Declaring global variables
temp = 0
tempmed = 0
temp_calibrated = 0
cpu_temp = 0
outside_temp = 0
outside_location = ""
outside_condition = ""
emoji = ""
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
    Polls the weather data from openweathermap API and returns values for global usage.
    """
    logger.debug('Retrieving condition from OWM.')

    global outside_temp
    global outside_condition
    global outside_location
    global emoji

    condfile = "owm_conditions.json"
    try:
        conditions = open(condfile,"r")
    except IOError:
        print "Condition map " + condfile + " not found!"

    cond = json.load(conditions)

    observation = owm.weather_at_zip_code(zip_code,country_code)
    w = observation.get_weather()
    outside_location = observation.get_location().get_name()
    outside_temp = round(w.get_temperature(unit)['temp'], 1)
    code = w.get_weather_code()
    outside_condition = ast.literal_eval(cond[str(code)])[0]
    emoji = ast.literal_eval(cond[str(code)])[1]

def get_temps():
    """Get measured temperatures from envirophat and raspberry pi CPU sensor.
    Calculate offset measured temp. Format for further use.
    """
    logger.debug('Calculating temperatures.')

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
    logger.debug('Sending message to Slack.')

    message = """It is currently %s in :flag-"""+str(country_code)+""":%s, %s\nOutside there is "%s" (%s) at:thermometer:%s C\nInside the office we have a temperature of :thermometer:%s C"""

    post = message % (str(currtime), zip_code, str(outside_location), str(outside_condition.title()), str(emoji), str(outside_temp), str(tempmed))

    # print message

    payload = {'text':post}
    requests.post(slack_webhook, json=payload)

def write_file():
    logger.debug('Logging data to enviro.log file.')

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
    get_condition()
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

def main():
    try:
        while True:
            logger.debug('Performing all updates.')
            perform_update()

            schedule.run_pending()

            time.sleep(30)

    except APICallError:
        logger.error('Problem calling OWM API.', exc_info=True)
        print("Error calling OWM API.")
        bot.sendMessage(user_id,"Tempi Script has crashed.")
        requests.post(slack_webhook, json={'text':':bug: Uhoh, something has gone wrong.'})
        time.sleep(300)
        main()
        pass

    except socket.error as serr:
        logger.error('Socket Error from OWM API.', exc_info=True)
        if serr.errno == 104:
            print("Error retrieving data from OWM Socket.")
            time.sleep(300)
            pass
        else:
            raise serr

    except KeyboardInterrupt:
        logger.info('User terminated application.')
        leds.off()
        out.close()
        # json_file.close()

    except:
        logger.error('Something has broken.', exc_info=True)

if __name__ == "__main__":
    main()
