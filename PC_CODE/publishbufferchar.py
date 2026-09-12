import paho.mqtt.client as mqtt


BROKER = "10.42.0.1"
PORT = 1883

USERNAME = "npdtom"
PASSWORD = "npd@tom"

TOPIC = "factory/fingerprint/M001/template"

FILE = "operator_001_template.bin"


with open(FILE, "rb") as f:
    template = f.read()


print("Template bytes:", len(template))


if len(template) != 768:
    raise SystemExit("Wrong template size")


client = mqtt.Client()

client.username_pw_set(
    USERNAME,
    PASSWORD
)


client.connect(
    BROKER,
    PORT,
    60
)


client.publish(
    TOPIC,
    payload=template,
    qos=1
)


client.disconnect()


print("Template published")