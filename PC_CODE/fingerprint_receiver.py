import json
import paho.mqtt.client as mqtt


# ============================
# MQTT CONFIG
# ============================

BROKER  = "10.42.0.1"
#BROKER = "10.10.10.248"
PORT = 1883

USERNAME = "npdtom"
PASSWORD = "npd@tom"

TOPIC_START = "factory/fingerprint/M001/start"
TOPIC_DATA = "factory/fingerprint/M001/data"
TOPIC_END = "factory/fingerprint/M001/end"


# ============================
# RECEIVE BUFFER
# ============================

fingerprint_buffer = bytearray()

expected_size = 0
expected_chunks = 0
received_chunks = 0


# ============================
# CONNECT
# ============================

def on_connect(client, userdata, flags, reason_code, properties):

    print("Connected to MQTT broker")

    client.subscribe(
        "factory/fingerprint/M001/#"
    )

    print("Waiting for fingerprint...")

def on_message(client, userdata, msg):

    global fingerprint_buffer
    global expected_size
    global expected_chunks
    global received_chunks


    # -------------------------
    # START
    # -------------------------

    if msg.topic == TOPIC_START:

        information = json.loads(
            msg.payload.decode()
        )

        expected_size = information["size"]
        expected_chunks = information["chunks"]

        fingerprint_buffer = bytearray()
        received_chunks = 0

        print()
        print("==============================")
        print("NEW FINGERPRINT")
        print("Machine:", information["machine_id"])
        print("Expected bytes:", expected_size)
        print("Expected chunks:", expected_chunks)
        print("==============================")


    # -------------------------
    # BINARY DATA
    # -------------------------

    elif msg.topic == TOPIC_DATA:

        fingerprint_buffer.extend(
            msg.payload
        )

        received_chunks += 1

        print(
            "Received:",
            received_chunks,
            "/",
            expected_chunks,
            "Total bytes:",
            len(fingerprint_buffer)
        )


    # -------------------------
    # END
    # -------------------------

    elif msg.topic == TOPIC_END:

        print()
        print("==============================")
        print("TRANSFER COMPLETE")
        print("Received chunks:", received_chunks)
        print("Received bytes:", len(fingerprint_buffer))
        print("==============================")


        if (
            len(fingerprint_buffer) == expected_size
            and
            received_chunks == expected_chunks
        ):

            print("SUCCESS: Fingerprint received correctly")

            with open(
                "fingerprint.raw",
                "wb"
            ) as file:

                file.write(
                    fingerprint_buffer
                )

            print(
                "Saved as fingerprint.raw"
            )

        else:

            print("ERROR: Fingerprint data incomplete")

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.username_pw_set(
    USERNAME,
    PASSWORD
)

client.on_connect = on_connect
client.on_message = on_message


print("Connecting to:", BROKER)

client.connect(
    BROKER,
    PORT,
    60
)

client.loop_forever()