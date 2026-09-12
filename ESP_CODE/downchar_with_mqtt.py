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

CLIENT_ID = "fingerprint_M001"

TOPIC_TEMPLATE = b"factory/fingerprint/M001/template"
TOPIC_ACK = b"factory/fingerprint/M001/ack"

PAGE_ID = 1

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

    packet = (
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

    return packet


# ============================================================
# SEND R307 COMMAND
# ============================================================

def send_command(instruction, params=b''):

    while uart.any():
        uart.read()

    data = bytes([instruction]) + params

    packet = build_packet(
        0x01,
        data
    )

    uart.write(packet)


# ============================================================
# READ R307 PACKET
# ============================================================

def read_packet(timeout_ms=3000):

    header = read_exact(
        9,
        timeout_ms
    )

    if header is None:

        print("Timeout reading R307 header")

        return None, None


    if header[0] != 0xEF or header[1] != 0x01:

        print("Invalid R307 header")

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

        print("Timeout reading R307 body")

        return None, None


    data = body[:-2]

    return packet_id, data


# ============================================================
# DOWNCHAR
# ============================================================

def downchar(template, buffer_id=0x01):

    print()
    print("================================")
    print("DOWNCHAR START")
    print("================================")

    print("Template bytes:", len(template))


    # DownChar = 0x09
    send_command(
        0x09,
        bytes([buffer_id])
    )


    pid, data = read_packet()


    if data is None:

        print("No response from R307")

        return False


    confirmation = data[0]

    print(
        "DownChar confirmation:",
        hex(confirmation)
    )


    if confirmation != 0x00:

        print("DownChar rejected")

        return False


    print("R307 ready to receive template")


    # -----------------------------------------
    # Send 128-byte packets
    # -----------------------------------------

    chunk_size = 128

    total_chunks = (
        len(template)
        + chunk_size
        - 1
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
            "Sent:",
            i + 1,
            "/",
            total_chunks,
            "PID:",
            hex(packet_id),
            "Bytes:",
            len(chunk)
        )


        time.sleep_ms(20)


    print("DownChar transfer complete")

    time.sleep_ms(300)

    return True


# ============================================================
# STORE TEMPLATE
# ============================================================

def store_template(
    page_id,
    buffer_id=0x01
):

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

        print("No Store response")

        return False


    confirmation = data[0]


    print(
        "Store confirmation:",
        hex(confirmation)
    )


    if confirmation == 0x00:

        print(
            "Template stored at PageID:",
            page_id
        )

        return True


    return False


# ============================================================
# MQTT ACK
# ============================================================

mqtt = None


def send_ack(status, message):

    payload = {
        "machine_id": "M001",
        "page_id": PAGE_ID,
        "status": status,
        "message": message
    }


    mqtt.publish(
        TOPIC_ACK,
        ujson.dumps(payload)
    )


    print(
        "MQTT ACK:",
        payload
    )


# ============================================================
# MQTT CALLBACK
# ============================================================

def mqtt_callback(topic, msg):

    print()
    print("================================")
    print("MQTT MESSAGE RECEIVED")
    print("================================")

    print("Topic:", topic)

    print(
        "Payload bytes:",
        len(msg)
    )


    # -----------------------------------------
    # Validate size
    # -----------------------------------------

    if len(msg) != EXPECTED_TEMPLATE_SIZE:

        print(
            "ERROR: Expected",
            EXPECTED_TEMPLATE_SIZE,
            "bytes"
        )

        send_ack(
            "failed",
            "invalid_template_size"
        )

        return


    print("Template size OK")


    # -----------------------------------------
    # DOWNCHAR
    # -----------------------------------------

    success = downchar(
        msg,
        buffer_id=0x01
    )


    if not success:

        send_ack(
            "failed",
            "downchar_failed"
        )

        return


    # -----------------------------------------
    # STORE
    # -----------------------------------------

    success = store_template(
        PAGE_ID,
        buffer_id=0x01
    )


    if not success:

        send_ack(
            "failed",
            "store_failed"
        )

        return


    # -----------------------------------------
    # SUCCESS
    # -----------------------------------------

    print()
    print("================================")
    print("TEMPLATE INSTALL SUCCESS")
    print("PageID:", PAGE_ID)
    print("================================")


    send_ack(
        "success",
        "template_installed"
    )


# ============================================================
# MQTT CONNECTION
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
        TOPIC_TEMPLATE
    )


    print("MQTT connected")

    print(
        "Subscribed:",
        TOPIC_TEMPLATE
    )


    return client


# ============================================================
# MAIN
# ============================================================

print()
print("================================")
print("FINGERPRINT MQTT RECEIVER")
print("================================")


wifi = connect_wifi()

mqtt = connect_mqtt()


print()
print("Waiting for fingerprint template...")
print()


while True:

    try:

        mqtt.check_msg()

        time.sleep_ms(100)


    except Exception as e:

        print(
            "MQTT error:",
            e
        )

        time.sleep(2)

        try:

            mqtt = connect_mqtt()

        except Exception as e:

            print(
                "Reconnect failed:",
                e
            )

            time.sleep(5)