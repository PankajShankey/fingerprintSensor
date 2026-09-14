from machine import UART, Pin
import time


# ============================================================
# R307 UART
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

TEMPLATE_FILE = "operator_004_template.bin"

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
# SEND COMMAND
# ============================================================

def send_command(instruction, params=b''):

    packet_id = 0x01

    length = 1 + len(params) + 2
    body = bytes([instruction]) + params

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

    while uart.any():
        uart.read()

    uart.write(packet)


# ============================================================
# READ ONE R307 PACKET
# ============================================================

def read_packet(timeout_ms=3000):

    header = read_exact(9, timeout_ms)

    if header is None:
        return None, None

    if header[0] != 0xEF or header[1] != 0x01:
        print("Invalid header")
        return None, None

    packet_id = header[6]

    length = (
        header[7] << 8
    ) | header[8]

    body = read_exact(length, timeout_ms)

    if body is None:
        return None, None

    # remove checksum
    data = body[:-2]

    return packet_id, data


# ============================================================
# COMMAND + ACK
# ============================================================

def command_ack(instruction, params=b'', timeout_ms=3000):

    send_command(instruction, params)

    pid, data = read_packet(timeout_ms)

    if data is None:
        return None

    return data[0]


# ============================================================
# GENIMG
# ============================================================

def capture_finger():

    return command_ack(0x01)


# ============================================================
# IMG2TZ
# ============================================================

def image_to_character(buffer_id):

    return command_ack(
        0x02,
        bytes([buffer_id])
    )


# ============================================================
# REGMODEL
# ============================================================

def create_model():

    return command_ack(0x05)


# ============================================================
# UPCHAR
# ============================================================

def upload_charbuffer(buffer_id):

    print()
    print("Uploading CharBuffer", buffer_id)

    send_command(
        0x08,
        bytes([buffer_id])
    )

    # ACK first
    pid, data = read_packet()

    if data is None:
        print("No UpChar ACK")
        return None

    code = data[0]

    print("UpChar confirmation:", hex(code))

    if code != 0x00:
        return None

    template = bytearray()

    packet_no = 0

    while True:

        pid, data = read_packet(timeout_ms=5000)

        if data is None:
            print("Timeout receiving template")
            return None

        packet_no += 1

        template.extend(data)

        print(
            "Packet:",
            packet_no,
            "PID:",
            hex(pid),
            "Bytes:",
            len(data),
            "Total:",
            len(template)
        )

        if pid == 0x08:
            break

        if pid != 0x02:
            print("Unexpected PID:", hex(pid))
            return None

    return bytes(template)


# ============================================================
# WAIT FOR FINGER
# ============================================================

def wait_for_finger():

    while True:

        code = capture_finger()

        if code == 0x00:
            return

        time.sleep_ms(300)


# ============================================================
# WAIT FOR FINGER REMOVAL
# ============================================================

def wait_for_removal():

    while True:

        code = capture_finger()

        if code == 0x02:
            return

        time.sleep_ms(300)


# ============================================================
# SAVE TEMPLATE TO ESP32
# ============================================================

def save_template(data, filename):

    with open(filename, "wb") as f:
        f.write(data)

    print()
    print("Template saved to:", filename)
    print("Saved bytes:", len(data))


# ============================================================
# MAIN ENROLLMENT TEST
# ============================================================

print()
print("========================================")
print("R307 TEMPLATE BACKUP TEST")
print("========================================")


# ------------------------------------------------------------
# CAPTURE 1
# ------------------------------------------------------------

print()
print("STEP 1")
print("Place finger on sensor...")

wait_for_finger()

print("First image captured")

code = image_to_character(0x01)

if code != 0x00:
    print("Img2Tz Buffer1 failed:", code)
    raise SystemExit

print("CharBuffer1 created")


# ------------------------------------------------------------
# REMOVE FINGER
# ------------------------------------------------------------

print()
print("Remove finger...")

wait_for_removal()

print("Finger removed")

time.sleep(1)


# ------------------------------------------------------------
# CAPTURE 2
# ------------------------------------------------------------

print()
print("STEP 2")
print("Place SAME finger again...")

wait_for_finger()

print("Second image captured")

code = image_to_character(0x02)

if code != 0x00:
    print("Img2Tz Buffer2 failed:", code)
    raise SystemExit

print("CharBuffer2 created")


# ------------------------------------------------------------
# REGMODEL
# ------------------------------------------------------------

print()
print("Creating final fingerprint model...")

code = create_model()

if code != 0x00:
    print("RegModel failed:", code)
    print("The two captures may not match.")
    raise SystemExit

print("RegModel successful")
print("Final template created")


# ------------------------------------------------------------
# UPCHAR FINAL TEMPLATE
# ------------------------------------------------------------

template = upload_charbuffer(0x01)

if template is None:
    print("Failed to upload final template")
    raise SystemExit


print()
print("========================================")
print("FINAL TEMPLATE RECEIVED")
print("========================================")
print("Template bytes:", len(template))


# ------------------------------------------------------------
# SAVE TEMPLATE
# ------------------------------------------------------------

save_template(
    template,
    TEMPLATE_FILE
)


# ------------------------------------------------------------
# VERIFY FILE
# ------------------------------------------------------------

with open(TEMPLATE_FILE, "rb") as f:
    verify_data = f.read()

print()
print("Read back bytes:", len(verify_data))

if verify_data == template:

    print("FILE VERIFY: OK")

else:

    print("FILE VERIFY: FAILED")


print()
print("========================================")
print("DO NOT CLEAR R307 YET")
print("Send me this output first.")
print("========================================")