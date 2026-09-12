from machine import UART, Pin
import time


# ============================================================
# CONFIGURATION
# ============================================================

TEMPLATE_FILE = "operator_001_template.bin"
PAGE_ID = 1

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
# READ EXACT BYTES
# ============================================================

def read_exact(count, timeout_ms=3000):

    data = bytearray()
    start = time.ticks_ms()

    while len(data) < count:

        if uart.any():

            chunk = uart.read(count - len(data))

            if chunk:
                data.extend(chunk)

        if time.ticks_diff(time.ticks_ms(), start) > timeout_ms:
            return None

        time.sleep_ms(1)

    return bytes(data)


# ============================================================
# BUILD COMMAND PACKET
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

    data = bytes([instruction]) + params

    packet = build_packet(
        0x01,
        data
    )

    uart.write(packet)


# ============================================================
# READ ONE R307 PACKET
# ============================================================

def read_packet(timeout_ms=3000):

    header = read_exact(9, timeout_ms)

    if header is None:
        print("Timeout reading packet header")
        return None, None

    if header[0] != 0xEF or header[1] != 0x01:
        print("Invalid R307 header")
        return None, None

    packet_id = header[6]

    length = (
        header[7] << 8
    ) | header[8]

    body = read_exact(length, timeout_ms)

    if body is None:
        print("Timeout reading packet body")
        return None, None

    # Last two bytes are checksum
    data = body[:-2]

    return packet_id, data


# ============================================================
# COMMAND + ACK
# ============================================================

def command_ack(instruction, params=b'', timeout_ms=3000):

    send_command(instruction, params)

    pid, data = read_packet(timeout_ms)

    if data is None or len(data) == 0:
        return None

    return data[0]


# ============================================================
# EMPTY R307 LIBRARY
#
# Empty = 0x0D
# ============================================================

def empty_library():

    print()
    print("Clearing R307 fingerprint library...")

    code = command_ack(0x0D)

    if code == 0x00:
        print("R307 LIBRARY CLEARED")
        return True

    print(
        "Failed to clear library:",
        hex(code) if code is not None else "None"
    )

    return False


# ============================================================
# SEND ONE DATA PACKET
# ============================================================

def send_data_packet(packet_id, data):

    packet = build_packet(
        packet_id,
        data
    )

    uart.write(packet)


# ============================================================
# DOWNCHAR
#
# DownChar = 0x09
# Buffer1 = 0x01
# ============================================================

def download_template(template, buffer_id=0x01):

    print()
    print("========================================")
    print("DOWNCHAR")
    print("========================================")

    print("Template bytes:", len(template))

    # Tell R307 that character data is coming
    send_command(
        0x09,
        bytes([buffer_id])
    )

    pid, data = read_packet()

    if data is None:
        print("No DownChar response")
        return False

    code = data[0]

    print("DownChar confirmation:", hex(code))

    if code != 0x00:
        print("R307 rejected DownChar")
        return False

    print("R307 ready to receive template")


    # ========================================================
    # SEND TEMPLATE
    #
    # Our R307 used 128-byte data packets during UpChar,
    # so use the same packet size for DownChar.
    # ========================================================

    chunk_size = 128

    total_chunks = (
        len(template) + chunk_size - 1
    ) // chunk_size

    for i in range(total_chunks):

        start = i * chunk_size
        end = start + chunk_size

        chunk = template[start:end]

        # Last packet = END DATA packet 0x08
        if i == total_chunks - 1:
            packet_id = 0x08

        # Other packets = DATA packet 0x02
        else:
            packet_id = 0x02

        send_data_packet(
            packet_id,
            chunk
        )

        print(
            "Sent packet:",
            i + 1,
            "/",
            total_chunks,
            "PID:",
            hex(packet_id),
            "Bytes:",
            len(chunk)
        )

        time.sleep_ms(20)


    print("Template transfer completed")

    # Give R307 a little time
    time.sleep_ms(300)

    return True


# ============================================================
# STORE CHARBUFFER1 INTO LIBRARY
#
# Store = 0x06
# ============================================================

def store_template(page_id, buffer_id=0x01):

    params = bytes([
        buffer_id,
        (page_id >> 8) & 0xFF,
        page_id & 0xFF
    ])

    code = command_ack(
        0x06,
        params
    )

    if code == 0x00:

        print()
        print("Template stored successfully")
        print("PageID:", page_id)

        return True

    print(
        "Store failed:",
        hex(code) if code is not None else "None"
    )

    return False


# ============================================================
# CAPTURE FINGER
# ============================================================

def capture_finger():

    return command_ack(0x01)


# ============================================================
# IMG2TZ -> CHARBUFFER1
# ============================================================

def image_to_character():

    return command_ack(
        0x02,
        bytes([0x01])
    )


# ============================================================
# SEARCH LIBRARY
# ============================================================

def search_library():

    # Buffer 1
    # Start page = 0
    # Search 1000 pages

    params = bytes([
        0x01,
        0x00, 0x00,
        0x03, 0xE8
    ])

    send_command(
        0x04,
        params
    )

    pid, data = read_packet()

    if data is None:
        return None, None, None

    code = data[0]

    if code == 0x00 and len(data) >= 5:

        page_id = (
            data[1] << 8
        ) | data[2]

        score = (
            data[3] << 8
        ) | data[4]

        return code, page_id, score

    return code, None, None


# ============================================================
# LOAD BACKUP FILE
# ============================================================

print()
print("========================================")
print("R307 TEMPLATE RESTORE TEST")
print("========================================")

print()
print("Reading:", TEMPLATE_FILE)

try:

    with open(TEMPLATE_FILE, "rb") as f:
        template = f.read()

except OSError:

    print("ERROR: Template file not found!")
    raise SystemExit


print("Template loaded from file")
print("Template bytes:", len(template))


# ============================================================
# SAFETY CHECK
# ============================================================

if len(template) != 768:

    print()
    print("ERROR: Expected the previously verified 768-byte template.")
    print("R307 WILL NOT BE CLEARED.")
    raise SystemExit


print("Backup size verification: OK")


# ============================================================
# CLEAR LIBRARY
# ============================================================

if not empty_library():

    raise SystemExit


# ============================================================
# RESTORE TEMPLATE INTO CHARBUFFER1
# ============================================================

if not download_template(
    template,
    buffer_id=0x01
):

    print("Template restore failed")
    raise SystemExit


# ============================================================
# STORE INTO PAGE ID 1
# ============================================================

print()
print("Storing restored template...")

if not store_template(
    PAGE_ID,
    buffer_id=0x01
):

    raise SystemExit


# ============================================================
# TEST WITH ACTUAL FINGER
# ============================================================

print()
print("========================================")
print("RESTORE COMPLETE")
print("========================================")
print()
print("Now place the SAME finger on the sensor...")


while True:

    code = capture_finger()

    if code == 0x00:
        break

    time.sleep_ms(300)


print("Finger captured")

code = image_to_character()

if code != 0x00:

    print(
        "Img2Tz failed:",
        hex(code) if code is not None else "None"
    )

    raise SystemExit


print("Fingerprint characteristics created")

code, page_id, score = search_library()


# ============================================================
# RESULT
# ============================================================

print()
print("========================================")

if code == 0x00:

    print("MATCH FOUND")
    print("Page ID :", page_id)
    print("Score   :", score)

    print()
    print("TEMPLATE BACKUP/RESTORE TEST: SUCCESS")

elif code == 0x09:

    print("NO MATCH")
    print()
    print("Template was restored but fingerprint did not match.")

else:

    print(
        "Search error:",
        hex(code) if code is not None else "None"
    )

print("========================================")