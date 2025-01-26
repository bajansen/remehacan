from remehacan import RemehaCAN
import paho.mqtt.client as paho
from time import sleep

from config import (
	MQTT_SERVER,
	MQTT_TOPIC_BASE,
	CAN_CHANNEL,
	CAN_INTERFACE
)

if __name__=="__main__":
	remeha = RemehaCAN(channel=CAN_CHANNEL, interface=CAN_INTERFACE, can_transmit=True)

	mqtt = paho.Client("remeha2mqtt")
	mqtt.connect(MQTT_SERVER)

	try:
		while True:
			data = remeha.datadict
			for datakey in data.keys():
				mqtt.publish(f"{MQTT_TOPIC_BASE}/{datakey}", data[datakey])
			sleep(5)
	except KeyboardInterrupt:
		pass
