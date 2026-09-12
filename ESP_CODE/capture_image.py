import network
import ujson
import time
from umqttsimple import MQTTClient

# =========================
# WIFI / MQTT
# =========================

SSID = "raspi5-iiot"
#SSID = "wifi2-iiot"
PASSWORD = "iota2024"

MQTT_SERVER = "10.42.0.1"
#MQTT_SERVER = "10.10.10.248"
MQTT_PORT = 1883
MQTT_USER = "npdtom"
MQTT_PASSWORD = "npd@tom"
#MQTT_USER = "npdAtom"
#MQTT_PASSWORD = "npd@Atom"

MACHINE_ID = "M001"

TOPIC_START = b"factory/fingerprint/M001/start"
TOPIC_DATA  = b"factory/fingerprint/M001/data"
TOPIC_END   = b"factory/fingerprint/M001/end"

CLIENT_ID = b"fingerprint_M001"

from machine import UART, Pin
import time
import gc


# ============================================================
# UART CONFIGURATION
# ============================================================

# Working wiring:
# R307 TX -> ESP32 GPIO14
# R307 RX -> ESP32 GPIO13

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
# READ EXACT NUMBER OF UART BYTES
# ============================================================

def read_exact(count, timeout_ms=3000):

    data = bytearray()

    start = time.ticks_ms()

    while len(data) < count:

        if uart.any():

            chunk = uart.read(count - len(data))

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
# READ ONE COMPLETE R307 PACKET
# ============================================================

def read_packet(timeout_ms=3000):

    # ------------------------------------
    # Header
    # ------------------------------------

    header = read_exact(2, timeout_ms)

    if header is None:
        return None

    if header != b'\xEF\x01':

        print("Invalid header:", header)
        return None


    # ------------------------------------
    # Address
    # ------------------------------------

    address = read_exact(4, timeout_ms)

    if address is None:
        return None


    # ------------------------------------
    # Packet identifier
    # ------------------------------------

    pid_data = read_exact(1, timeout_ms)

    if pid_data is None:
        return None

    pid = pid_data[0]


    # ------------------------------------
    # Packet length
    # ------------------------------------

    length_data = read_exact(2, timeout_ms)

    if length_data is None:
        return None

    length = (
        length_data[0] << 8
    ) | length_data[1]


    # length includes:
    #
    # DATA
    # +
    # 2 checksum bytes

    remaining = read_exact(
        length,
        timeout_ms
    )

    if remaining is None:
        return None


    # Last two bytes = checksum
    payload = remaining[:-2]

    checksum = (
        remaining[-2] << 8
    ) | remaining[-1]


    return {
        "pid": pid,
        "payload": payload,
        "checksum": checksum,
        "length": length
    }


# ============================================================
# SEND COMMAND
# ============================================================

def send_command(instruction, params=b''):

    packet_id = 0x01

    body = bytes([instruction]) + params

    length = len(body) + 2

    checksum = (
        packet_id
        + ((length >> 8) & 0xFF)
        + (length & 0xFF)
        + sum(body)
    ) & 0xFFFF


    packet = (
        b'\xEF\x01'
        + ADDRESS
        + bytes([packet_id])
        + bytes([
            (length >> 8) & 0xFF,
            length & 0xFF
        ])
        + body
        + bytes([
            (checksum >> 8) & 0xFF,
            checksum & 0xFF
        ])
    )


    # Clear UART buffer
    while uart.any():
        uart.read()


    uart.write(packet)


# ============================================================
# CAPTURE FINGER
# ============================================================

def capture_finger():

    print("Waiting for finger...")

    while True:

        # GenImg = 0x01
        send_command(0x01)

        packet = read_packet()

        if packet is None:

            print("No response")
            time.sleep_ms(300)
            continue


        code = packet["payload"][0]


        if code == 0x00:

            print("Fingerprint captured.")
            return True


        elif code == 0x02:

            # No finger
            time.sleep_ms(300)


        else:

            print(
                "Capture error:",
                hex(code)
            )

            time.sleep_ms(500)


# ============================================================
# UPLOAD IMAGE
# ============================================================

def upload_image():

    print()
    print("Requesting fingerprint image...")

    # UpImage command = 0x0A
    send_command(0x0A)


    # ========================================================
    # First packet should be ACK
    # ========================================================

    ack = read_packet()

    if ack is None:

        print("ERROR: No ACK received")
        return None


    if ack["pid"] != 0x07:

        print(
            "ERROR: Unexpected ACK PID:",
            hex(ack["pid"])
        )
        return None


    confirmation = ack["payload"][0]

    print(
        "UpImage confirmation:",
        hex(confirmation)
    )


    if confirmation != 0x00:

        print("ERROR: R307 refused image upload")
        return None


    print("R307 ready to transfer image.")


    # ========================================================
    # Receive image packets
    # ========================================================

    image = bytearray()

    packet_count = 0


    while True:

        packet = read_packet(
            timeout_ms=5000
        )


        if packet is None:

            print("ERROR: Image packet timeout")
            return None


        pid = packet["pid"]

        payload = packet["payload"]

        image.extend(payload)

        packet_count += 1


        print(
            "Packet:",
            packet_count,
            "PID:",
            hex(pid),
            "Data:",
            len(payload),
            "Total:",
            len(image)
        )


        # ----------------------------------------
        # PID 0x08 = End of data
        # ----------------------------------------

        if pid == 0x08:

            print("End packet received.")
            break


        # ----------------------------------------
        # PID 0x02 = normal data packet
        # ----------------------------------------

        elif pid != 0x02:

            print(
                "Unexpected packet type:",
                hex(pid)
            )

            return None


    return image


def connect_wifi():

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():

        print("Connecting WiFi...")

        wlan.connect(SSID, PASSWORD)

        timeout = 20

        while not wlan.isconnected() and timeout > 0:
            print(".", end="")
            time.sleep(1)
            timeout -= 1

    if not wlan.isconnected():
        raise Exception("WiFi connection failed")

    print()
    print("WiFi connected")
    print("ESP32 IP:", wlan.ifconfig()[0])

    return wlan


def connect_mqtt():

    print("Connecting MQTT...")

    client = MQTTClient(
        CLIENT_ID,
        MQTT_SERVER,
        port=MQTT_PORT,
        user=MQTT_USER,
        password=MQTT_PASSWORD
    )

    client.connect()

    print("MQTT connected:", MQTT_SERVER)

    return client

def publish_fingerprint(client, image_data):

    CHUNK_SIZE = 1024

    total_size = len(image_data)

    total_chunks = (
        total_size + CHUNK_SIZE - 1
    ) // CHUNK_SIZE

    print()
    print("==============================")
    print("Publishing fingerprint")
    print("Size:", total_size)
    print("Chunks:", total_chunks)
    print("==============================")


    # ---------------------------------
    # START MESSAGE
    # ---------------------------------

    start_message = {
        "machine_id": MACHINE_ID,
        "size": total_size,
        "chunk_size": CHUNK_SIZE,
        "chunks": total_chunks
    }

    client.publish(
        TOPIC_START,
        ujson.dumps(start_message)
    )

    print("START published")


    # ---------------------------------
    # BINARY DATA
    # ---------------------------------

    for chunk_number in range(total_chunks):

        start = chunk_number * CHUNK_SIZE
        end = start + CHUNK_SIZE

        chunk = image_data[start:end]

        client.publish(
            TOPIC_DATA,
            chunk
        )

        print(
            "Published chunk",
            chunk_number + 1,
            "/",
            total_chunks,
            "bytes:",
            len(chunk)
        )

        # Small gap so we don't flood broker/network
        time.sleep_ms(30)


    # ---------------------------------
    # END MESSAGE
    # ---------------------------------

    end_message = {
        "machine_id": MACHINE_ID,
        "size": total_size,
        "chunks": total_chunks
    }

    client.publish(
        TOPIC_END,
        ujson.dumps(end_message)
    )

    print("END published")
    
# ============================================================
# MAIN
# ============================================================
print()
print("==============================")
print("CENTRAL FINGERPRINT MQTT PoC")
print("==============================")


# WiFi
wlan = connect_wifi()


# MQTT
mqtt = connect_mqtt()


# Capture fingerprint
capture_finger()


# Get 36,864-byte image from R307
image_data = upload_image()


if image_data is not None:

    print()
    print("Fingerprint image received")
    print("Bytes:", len(image_data))

    if len(image_data) == 36864:

        print("Image size correct")

        publish_fingerprint(
            mqtt,
            image_data
        )

        print()
        print("==============================")
        print("FINGERPRINT SENT TO PC")
        print("==============================")

    else:

        print(
            "ERROR: Unexpected image size:",
            len(image_data)
        )


mqtt.disconnect()