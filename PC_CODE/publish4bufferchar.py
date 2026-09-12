import json
import time
import threading
import paho.mqtt.client as mqtt


# ============================================================
# MQTT
# ============================================================

BROKER = "10.42.0.1"
PORT = 1883

USERNAME = "npdtom"
PASSWORD = "npd@tom"

TOPIC_COMMAND = "factory/fingerprint/M001/command"
TOPIC_TEMPLATE = "factory/fingerprint/M001/template"
TOPIC_ACK = "factory/fingerprint/M001/ack"


# ============================================================
# OPERATORS
# ============================================================

operators = [

    {
        "operator_id": "EMP001",
        "page_id": 1,
        "file": "operator_001_template.bin"
    },

    {
        "operator_id": "EMP002",
        "page_id": 2,
        "file": "operator_002_template.bin"
    },

    {
        "operator_id": "EMP003",
        "page_id": 3,
        "file": "operator_003_template.bin"
    },

    {
        "operator_id": "EMP004",
        "page_id": 4,
        "file": "operator_004_template.bin"
    }
]


# ============================================================
# GLOBAL ACK STATE
# ============================================================

ack_event = threading.Event()

last_ack = None


# ============================================================
# MQTT CALLBACK
# ============================================================

def on_connect(client, userdata, flags, rc):

    print("MQTT connected:", rc)

    client.subscribe(
        TOPIC_ACK,
        qos=1
    )


def on_message(client, userdata, msg):

    global last_ack

    try:

        payload = json.loads(
            msg.payload.decode()
        )

    except Exception as e:

        print("Invalid ACK:", e)
        return


    print()
    print("ACK RECEIVED:")
    print(payload)

    last_ack = payload

    ack_event.set()


# ============================================================
# WAIT FOR SPECIFIC ACK
# ============================================================

def wait_for_ack(command_id, wanted_status, timeout=10):

    global last_ack

    start = time.time()

    while time.time() - start < timeout:

        remaining = timeout - (
            time.time() - start
        )

        ack_event.wait(
            timeout=max(0.1, remaining)
        )

        ack_event.clear()


        if last_ack is None:
            continue


        if (
            last_ack.get("command_id") == command_id
            and
            last_ack.get("status") == wanted_status
        ):

            return last_ack


        # Immediate failure
        if (
            last_ack.get("command_id") == command_id
            and
            last_ack.get("status") == "failed"
        ):

            return last_ack


    return None


# ============================================================
# MQTT CLIENT
# ============================================================

client = mqtt.Client(
    client_id="fingerprint_server_sync"
)

client.username_pw_set(
    USERNAME,
    PASSWORD
)

client.on_connect = on_connect
client.on_message = on_message

client.connect(
    BROKER,
    PORT,
    60
)

client.loop_start()

time.sleep(1)


# ============================================================
# SEND OPERATORS ONE BY ONE
# ============================================================

for index, operator in enumerate(operators, start=1):

    operator_id = operator["operator_id"]

    page_id = operator["page_id"]

    filename = operator["file"]


    print()
    print("========================================")
    print(
        "OPERATOR",
        index,
        "/",
        len(operators)
    )
    print("========================================")

    print("Operator:", operator_id)
    print("PageID:", page_id)
    print("File:", filename)


    # --------------------------------------------------------
    # READ TEMPLATE
    # --------------------------------------------------------

    with open(filename, "rb") as f:

        template = f.read()


    print("Template bytes:", len(template))


    if len(template) != 768:

        print("ERROR: Invalid template size")
        break


    # --------------------------------------------------------
    # UNIQUE COMMAND ID
    # --------------------------------------------------------

    command_id = (
        "CMD-"
        + operator_id
        + "-"
        + str(int(time.time()))
    )


    command = {

        "command_id": command_id,

        "action": "add_template",

        "operator_id": operator_id,

        "page_id": page_id,

        "template_size": len(template)
    }


    # --------------------------------------------------------
    # SEND COMMAND
    # --------------------------------------------------------

    print()
    print("Sending command...")

    last_ack = None
    ack_event.clear()


    client.publish(
        TOPIC_COMMAND,
        json.dumps(command),
        qos=1
    )


    # --------------------------------------------------------
    # WAIT FOR READY
    # --------------------------------------------------------

    print("Waiting for READY ACK...")


    ack = wait_for_ack(
        command_id,
        "ready",
        timeout=10
    )


    if ack is None:

        print("ERROR: No READY response")
        break


    if ack.get("status") == "failed":

        print("ESP32 rejected command")
        break


    print("ESP32 ready")


    # --------------------------------------------------------
    # SEND TEMPLATE
    # --------------------------------------------------------

    print("Sending template...")


    last_ack = None
    ack_event.clear()


    client.publish(
        TOPIC_TEMPLATE,
        payload=template,
        qos=1
    )


    # --------------------------------------------------------
    # WAIT FOR SUCCESS
    # --------------------------------------------------------

    print("Waiting for INSTALL ACK...")


    ack = wait_for_ack(
        command_id,
        "success",
        timeout=15
    )


    if ack is None:

        print("ERROR: No install ACK")
        break


    if ack.get("status") == "failed":

        print(
            "INSTALL FAILED:",
            ack
        )

        break


    print()
    print(
        operator_id,
        "installed successfully at PageID",
        page_id
    )


    time.sleep(0.5)


else:

    print()
    print("========================================")
    print("ALL 4 OPERATORS INSTALLED SUCCESSFULLY")
    print("========================================")


client.loop_stop()
client.disconnect()