from machine import UART, Pin
import time


# ============================================================
# R307 UART
# R307 TX -> ESP32 GPIO14 (RX)
# R307 RX -> ESP32 GPIO13 (TX)
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
# SEND COMMAND
# ============================================================

def send_command(instruction, params=b'', timeout_ms=2000):

    packet_id = 0x01

    # instruction + parameters + checksum(2 bytes)
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

    # Clear old UART data
    while uart.any():
        uart.read()

    uart.write(packet)

    start = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:

        if uart.any():

            time.sleep_ms(50)

            response = uart.read()

            return response

        time.sleep_ms(10)

    return None


# ============================================================
# GET CONFIRMATION CODE
# ============================================================

def confirmation(response):

    if response is None:
        return None

    if len(response) < 10:
        return None

    return response[9]


# ============================================================
# CAPTURE FINGERPRINT IMAGE
# GenImg = 0x01
# ============================================================

def capture_finger():

    return send_command(0x01)


# ============================================================
# IMAGE -> CHARACTER BUFFER
#
# Img2Tz = 0x02
#
# Buffer 1 = 0x01
# Buffer 2 = 0x02
# ============================================================

def image_to_character(buffer_id):

    return send_command(
        0x02,
        bytes([buffer_id])
    )


# ============================================================
# CREATE TEMPLATE
#
# RegModel = 0x05
#
# Combines CharBuffer1 and CharBuffer2
# ============================================================

def create_model():

    return send_command(0x05)


# ============================================================
# STORE TEMPLATE
#
# Store = 0x06
#
# Params:
# BufferID
# PageID high byte
# PageID low byte
# ============================================================

def store_template(page_id, buffer_id=0x01):

    params = bytes([
        buffer_id,
        (page_id >> 8) & 0xFF,
        page_id & 0xFF
    ])

    return send_command(
        0x06,
        params
    )


# ============================================================
# WAIT UNTIL FINGER IS PLACED
# ============================================================

def wait_for_finger():

    while True:

        response = capture_finger()

        code = confirmation(response)

        if code == 0x00:
            return True

        time.sleep_ms(300)


# ============================================================
# WAIT UNTIL FINGER IS REMOVED
# ============================================================

def wait_for_finger_remove():

    while True:

        response = capture_finger()

        code = confirmation(response)

        # 0x02 = no finger detected
        if code == 0x02:
            return True

        time.sleep_ms(300)


# ============================================================
# ENROLL FINGER
# ============================================================

def enroll_finger(page_id):

    print()
    print("========================================")
    print("R307 FINGERPRINT ENROLLMENT")
    print("========================================")
    print("Page ID:", page_id)
    print()


    # ========================================================
    # FIRST CAPTURE
    # ========================================================

    print("STEP 1")
    print("Place finger on sensor...")

    wait_for_finger()

    print("Finger detected")
    print("Image captured")

    response = image_to_character(0x01)

    code = confirmation(response)

    if code != 0x00:

        print("ERROR creating CharBuffer1")

        if code is not None:
            print("Confirmation:", hex(code))

        return False

    print("CharBuffer1 created successfully")


    # ========================================================
    # REMOVE FINGER
    # ========================================================

    print()
    print("Remove finger from sensor...")

    wait_for_finger_remove()

    print("Finger removed")

    time.sleep(1)


    # ========================================================
    # SECOND CAPTURE
    # ========================================================

    print()
    print("STEP 2")
    print("Place SAME finger again...")

    wait_for_finger()

    print("Finger detected")
    print("Second image captured")

    response = image_to_character(0x02)

    code = confirmation(response)

    if code != 0x00:

        print("ERROR creating CharBuffer2")

        if code is not None:
            print("Confirmation:", hex(code))

        return False

    print("CharBuffer2 created successfully")


    # ========================================================
    # GENERATE TEMPLATE
    # ========================================================

    print()
    print("Creating fingerprint template...")

    response = create_model()

    code = confirmation(response)

    if code != 0x00:

        print("ERROR: Two fingerprint captures do not match")

        if code is not None:
            print("Confirmation:", hex(code))

        return False

    print("Fingerprint template created successfully")


    # ========================================================
    # STORE TEMPLATE
    # ========================================================

    print()
    print("Storing template at PageID:", page_id)

    response = store_template(
        page_id,
        buffer_id=0x01
    )

    code = confirmation(response)

    if code != 0x00:

        print("ERROR storing fingerprint")

        if code is not None:
            print("Confirmation:", hex(code))

        return False


    # ========================================================
    # SUCCESS
    # ========================================================

    print()
    print("========================================")
    print("ENROLLMENT SUCCESSFUL")
    print("Fingerprint stored at PageID:", page_id)
    print("========================================")
    print()

    return True


# ============================================================
# MAIN
# ============================================================

# Change this number for every new fingerprint
PAGE_ID = 2

enroll_finger(PAGE_ID)