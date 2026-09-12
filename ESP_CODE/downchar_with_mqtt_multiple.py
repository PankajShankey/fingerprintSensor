from machine import UART, Pin
import time
import network
import ujson

from umqttsimple import MQTTClient


# ============================================================
# CONFIG
# ============================================================

WIFI_SSID = "raspi5-iiot"
WIFI_PASSWORD = "iota2024"

MQTT_BROKER = "10.42.0.1"
MQTT_PORT = 1883

MQTT_USERNAME = "npdtom"
MQTT_PASSWORD = "npd@tom"

MACHINE_ID = "M001"

CLIENT_ID = "fingerprint_M001_sync"

TOPIC_COMMAND = b"factory/fingerprint/M001/command"
TOPIC_TEMPLATE = b"factory/fingerprint/M001/template"
TOPIC_ACK = b"factory/fingerprint/M001/ack"

EXPECTED_TEMPLATE_SIZE = 768


# ============================================================
# R307 UART
#
# R307 TX -> ESP32 GPIO14
# R307 RX -> ESP32 GPIO13
# ============================================================

uart = UART(
    2,
    baudrate=57600,
    bits=8,
    parity=None,
    stop=1,
    rx=Pin(14),
    tx=Pin(13)
)

ADDRESS = b'\xFF\xFF\xFF\xFF'

time.sleep_ms(500)


# ============================================================
# GLOBALS
# ============================================================

mqtt = None
pending_command = None


# ============================================================
# WIFI
# ============================================================

def connect_wifi():

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        print("WiFi already connected")
        print(wlan.ifconfig())
        return wlan

    print("Connecting WiFi...")

    wlan.connect(
        WIFI_SSID,
        WIFI_PASSWORD
    )

    timeout = 20

    while not wlan.isconnected() and timeout > 0:

        print(".", end="")
        time.sleep(1)
        timeout -= 1

    print()

    if not wlan.isconnected():
        raise RuntimeError("WiFi connection failed")

    print("WiFi connected")
    print(wlan.ifconfig())

    return wlan


# ============================================================
# R307 READ EXACT
# ============================================================

def read_exact(count, timeout_ms=3000):

    data = bytearray()
    start = time.ticks_ms()

    while len(data) < count:

        if uart.any():

            chunk = uart.read(
                count - len(data)
            )

            if chunk:
                data.extend(chunk)

        if time.ticks_diff(
            time.ticks_ms(),
            start
        ) > timeout_ms:

            return None

        time.sleep_ms(1)

    return bytes(data)


# ============================================================
# BUILD R307 PACKET
# ============================================================

def build_packet(packet_id, data):

    length = len(data) + 2

    checksum = (
        packet_id
        + ((length >> 8) & 0xFF)
        + (length & 0xFF)
        + sum(data)
    ) & 0xFFFF

    return (
        b'\xEF\x01'
        + ADDRESS
        + bytes([packet_id])
        + bytes([
            (length >> 8) & 0xFF,
            length & 0xFF
        ])
        + data
        + bytes([
            (checksum >> 8) & 0xFF,
            checksum & 0xFF
        ])
    )


# ============================================================
# SEND COMMAND
# ============================================================

def send_command(instruction, params=b''):

    while uart.any():
        uart.read()

    packet = build_packet(
        0x01,
        bytes([instruction]) + params
    )

    uart.write(packet)


# ============================================================
# READ R307 PACKET
# ============================================================

def read_packet(timeout_ms=3000):

    header = read_exact(9, timeout_ms)

    if header is None:
        print("R307 header timeout")
        return None, None

    if header[0] != 0xEF or header[1] != 0x01:
        print("Invalid R307 packet")
        return None, None

    packet_id = header[6]

    length = (
        header[7] << 8
    ) | header[8]

    body = read_exact(
        length,
        timeout_ms
    )

    if body is None:
        print("R307 body timeout")
        return None, None

    return packet_id, body[:-2]


# ============================================================
# DOWNCHAR
# ============================================================

def downchar(template, buffer_id=0x01):

    print()
    print("DOWNCHAR")
    print("Template bytes:", len(template))

    # DownChar = 0x09
    send_command(
        0x09,
        bytes([buffer_id])
    )

    pid, data = read_packet()

    if data is None:
        return False

    code = data[0]

    print("DownChar confirmation:", hex(code))

    if code != 0x00:
        return False


    # --------------------------------------------------------
    # Transfer in same 128-byte format proven earlier
    # --------------------------------------------------------

    chunk_size = 128

    total_chunks = (
        len(template) + chunk_size - 1
    ) // chunk_size

    for i in range(total_chunks):

        start = i * chunk_size
        end = start + chunk_size

        chunk = template[start:end]

        if i == total_chunks - 1:
            packet_id = 0x08
        else:
            packet_id = 0x02

        packet = build_packet(
            packet_id,
            chunk
        )

        uart.write(packet)

        print(
            "Packet",
            i + 1,
            "/",
            total_chunks,
            "PID",
            hex(packet_id)
        )

        time.sleep_ms(20)

    time.sleep_ms(300)

    return True


# ============================================================
# STORE TEMPLATE
# ============================================================

def store_template(page_id, buffer_id=0x01):

    params = bytes([
        buffer_id,
        (page_id >> 8) & 0xFF,
        page_id & 0xFF
    ])

    # Store = 0x06
    send_command(
        0x06,
        params
    )

    pid, data = read_packet()

    if data is None:
        return False

    code = data[0]

    print("Store confirmation:", hex(code))

    return code == 0x00


# ============================================================
# MQTT ACK
# ============================================================

def send_ack(
    command_id,
    operator_id,
    page_id,
    status,
    message
):

    payload = {
        "command_id": command_id,
        "machine_id": MACHINE_ID,
        "operator_id": operator_id,
        "page_id": page_id,
        "status": status,
        "message": message
    }

    mqtt.publish(
        TOPIC_ACK,
        ujson.dumps(payload),
        qos=1
    )

    print("ACK:", payload)


# ============================================================
# PROCESS COMMAND
# ============================================================

def process_command(msg):

    global pending_command

    try:

        command = ujson.loads(msg)

    except Exception as e:

        print("Invalid JSON:", e)
        return


    if command.get("action") != "add_template":

        print("Unknown action")
        return


    command_id = command.get("command_id")
    operator_id = command.get("operator_id")
    page_id = command.get("page_id")
    template_size = command.get("template_size")


    if (
        command_id is None
        or operator_id is None
        or page_id is None
    ):

        print("Missing command data")
        return


    if template_size != EXPECTED_TEMPLATE_SIZE:

        send_ack(
            command_id,
            operator_id,
            page_id,
            "failed",
            "invalid_template_size"
        )

        return


    pending_command = command


    print()
    print("================================")
    print("NEW TEMPLATE COMMAND")
    print("================================")
    print("Command ID :", command_id)
    print("Operator   :", operator_id)
    print("PageID     :", page_id)
    print("Size       :", template_size)


    # Tell PC it can now send binary template
    send_ack(
        command_id,
        operator_id,
        page_id,
        "ready",
        "send_template"
    )


# ============================================================
# PROCESS TEMPLATE
# ============================================================

def process_template(msg):

    global pending_command


    if pending_command is None:

        print("Template received without command")
        return


    command_id = pending_command["command_id"]
    operator_id = pending_command["operator_id"]
    page_id = pending_command["page_id"]


    print()
    print("================================")
    print("TEMPLATE RECEIVED")
    print("================================")
    print("Operator:", operator_id)
    print("PageID:", page_id)
    print("Bytes:", len(msg))


    if len(msg) != EXPECTED_TEMPLATE_SIZE:

        send_ack(
            command_id,
            operator_id,
            page_id,
            "failed",
            "wrong_binary_size"
        )

        pending_command = None
        return


    # --------------------------------------------------------
    # DOWNCHAR
    # --------------------------------------------------------

    if not downchar(msg, 0x01):

        send_ack(
            command_id,
            operator_id,
            page_id,
            "failed",
            "downchar_failed"
        )

        pending_command = None
        return


    # --------------------------------------------------------
    # STORE
    # --------------------------------------------------------

    if not store_template(page_id, 0x01):

        send_ack(
            command_id,
            operator_id,
            page_id,
            "failed",
            "store_failed"
        )

        pending_command = None
        return


    print()
    print("================================")
    print("INSTALL SUCCESS")
    print("Operator:", operator_id)
    print("PageID:", page_id)
    print("================================")


    send_ack(
        command_id,
        operator_id,
        page_id,
        "success",
        "template_installed"
    )


    pending_command = None


# ============================================================
# MQTT CALLBACK
# ============================================================

def mqtt_callback(topic, msg):

    if topic == TOPIC_COMMAND:

        process_command(msg)

    elif topic == TOPIC_TEMPLATE:

        process_template(msg)


# ============================================================
# MQTT CONNECT
# ============================================================

def connect_mqtt():

    print("Connecting MQTT...")

    client = MQTTClient(
        CLIENT_ID,
        MQTT_BROKER,
        port=MQTT_PORT,
        user=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        keepalive=60
    )

    client.set_callback(
        mqtt_callback
    )

    client.connect()

    client.subscribe(
        TOPIC_COMMAND,
        qos=1
    )

    client.subscribe(
        TOPIC_TEMPLATE,
        qos=1
    )

    print("MQTT connected")
    print("Subscribed:", TOPIC_COMMAND)
    print("Subscribed:", TOPIC_TEMPLATE)

    return client


# ============================================================
# MAIN
# ============================================================

print()
print("================================")
print("R307 MULTI-OPERATOR SYNC")
print("================================")

wifi = connect_wifi()

mqtt = connect_mqtt()

print()
print("Waiting for operator templates...")
print()


while True:

    try:

        mqtt.check_msg()

        time.sleep_ms(50)

    except Exception as e:

        print("MQTT ERROR:", e)

        time.sleep(2)

        try:

            mqtt = connect_mqtt()

        except Exception as e:

            print("Reconnect failed:", e)
            time.sleep(5)