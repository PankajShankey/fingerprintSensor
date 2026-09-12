from machine import UART, Pin
import time

# ============================================================
# R307 UART
# Working connection:
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

time.sleep_ms(500)

ADDRESS = b'\xFF\xFF\xFF\xFF'


# ============================================================
# Create and send R307 command
# ============================================================

def send_command(instruction, params=b'', timeout_ms=2000):

    packet_id = 0x01

    length = 1 + len(params) + 2
    body = bytes([instruction]) + params

    checksum = (
        packet_id +
        ((length >> 8) & 0xFF) +
        (length & 0xFF) +
        sum(body)
    ) & 0xFFFF

    packet = (
        b'\xEF\x01' +
        b'\xFF\xFF\xFF\xFF' +
        bytes([packet_id]) +
        bytes([
            (length >> 8) & 0xFF,
            length & 0xFF
        ]) +
        body +
        bytes([
            (checksum >> 8) & 0xFF,
            checksum & 0xFF
        ])
    )

    # Clear previous data
    while uart.any():
        uart.read()

    print(
        "TX:",
        " ".join("{:02X}".format(x) for x in packet)
    )

    uart.write(packet)

    # ------------------------------------
    # Wait for R307 response
    # ------------------------------------
    start = time.ticks_ms()

    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:

        if uart.any():
            time.sleep_ms(50)

            response = uart.read()

            print(
                "RX:",
                " ".join("{:02X}".format(x) for x in response)
            )

            return response

        time.sleep_ms(10)

    print("ERROR: R307 response timeout")

    return None


# ============================================================
# Get confirmation code
# ============================================================

def confirmation(response):

    if response is None:
        return None

    if len(response) < 10:
        return None

    return response[9]


# ============================================================
# Wait for finger
# GenImg = 0x01
# ============================================================

def wait_for_finger():

    while True:

        response = send_command(0x01)

        code = confirmation(response)

        if code == 0x00:
            print("Fingerprint captured.")
            return True

        elif code == 0x02:
            print("Waiting for finger...")

        else:
            print("Capture error:", code)

        time.sleep_ms(500)


# ============================================================
# Wait until finger removed
# ============================================================

def wait_finger_removed():

    print("\nRemove finger...")

    while True:

        response = send_command(0x01)

        code = confirmation(response)

        if code == 0x02:
            print("Finger removed.")
            return

        time.sleep_ms(300)


# ============================================================
# Convert image to character
# Img2Tz = 0x02
# ============================================================

def image_to_character(buffer_id):

    response = send_command(
        0x02,
        bytes([buffer_id])
    )

    return confirmation(response) == 0x00


# ============================================================
# Generate template
# RegModel = 0x05
# ============================================================

def create_template():

    response = send_command(0x05)

    return confirmation(response) == 0x00


# ============================================================
# Store template
# Store = 0x06
# ============================================================

def store_template(page_id):

    params = bytes([
        0x01,                    # CharBuffer1
        (page_id >> 8) & 0xFF,
        page_id & 0xFF
    ])

    response = send_command(
        0x06,
        params
    )

    return confirmation(response) == 0x00


# ============================================================
# ENROLL
# ============================================================

def enroll(page_id):

    print("\n================================")
    print("R307 Fingerprint Enrollment")
    print("Page ID:", page_id)
    print("================================")

    # --------------------------------------------------------
    # First scan
    # --------------------------------------------------------

    print("\nSTEP 1")
    print("Place finger on sensor...")

    wait_for_finger()

    print("Converting first fingerprint...")

    if not image_to_character(1):
        print("ERROR: Failed to create CharBuffer1")
        return

    print("First fingerprint OK.")

    # --------------------------------------------------------
    # Remove finger
    # --------------------------------------------------------

    wait_finger_removed()

    time.sleep(1)

    # --------------------------------------------------------
    # Second scan
    # --------------------------------------------------------

    print("\nSTEP 2")
    print("Place SAME finger again...")

    wait_for_finger()

    print("Converting second fingerprint...")

    if not image_to_character(2):
        print("ERROR: Failed to create CharBuffer2")
        return

    print("Second fingerprint OK.")

    # --------------------------------------------------------
    # Generate template
    # --------------------------------------------------------

    print("\nCreating fingerprint template...")

    if not create_template():
        print("ERROR: Both fingerprints do not match.")
        return

    print("Template created.")

    # --------------------------------------------------------
    # Store
    # --------------------------------------------------------

    print("Storing fingerprint as ID:", page_id)

    if not store_template(page_id):
        print("ERROR: Could not store fingerprint.")
        return

    print("\n================================")
    print("SUCCESS")
    print("Fingerprint enrolled as ID:", page_id)
    print("================================")


# ============================================================
# Start enrollment
# ============================================================

enroll(1)