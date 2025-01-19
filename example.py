from remehacan import RemehaCAN
import paho.mqtt.client as paho

from config import (
    MQTT_SERVER,
    MQTT_TOPIC_BASE,
    CAN_CHANNEL,
    CAN_INTERFACE
)

if __name__=="__main__":
	remeha = RemehaCAN(CAN_CHANNEL, CAN_INTERFACE)

	mqtt = paho.Client("remeha2mqtt")
	mqtt.connect(MQTT_SERVER)

	try:
		while True:
			data = remeha.parse_message((remeha.receive_msg()))
			if data != None:
				for datakey in data.keys():
					mqtt.publish(f"{MQTT_TOPIC_BASE}/{datakey}", data[datakey])
	except KeyboardInterrupt:
		pass
