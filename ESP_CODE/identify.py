from machine import UART, Pin
import time

# Output pin
# ============================================================
# STATUS LEDs
# ============================================================

GREEN_LED = Pin(4, Pin.OUT)
RED_LED   = Pin(3, Pin.OUT)

# Start with both OFF
GREEN_LED.value(0)
RED_LED.value(0)

# How long output stays ON
#OUTPUT_ON_TIME = 60   # seconds

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
# Send R307 command
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
        ADDRESS +
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


def confirmation(response):

    if response is None or len(response) < 10:
        return None

    return response[9]


# ============================================================
# Capture fingerprint
# ============================================================

def capture_finger():

    return send_command(0x01)


# ============================================================
# Convert fingerprint -> CharBuffer1
# ============================================================

def image_to_character():

    return send_command(
        0x02,
        bytes([0x01])
    )


# ============================================================
# Search fingerprint library
# ============================================================

def search_finger():

    # Buffer ID = 1
    # Start Page = 0
    # Number of pages = 1000

    params = bytes([
        0x01,       # CharBuffer1

        0x00, 0x00, # Start Page = 0

        0x03, 0xE8  # Search 1000 templates
    ])

    return send_command(
        0x04,
        params
    )


# ============================================================
# Main identification loop
# ============================================================

print()
print("================================")
print("R307 Fingerprint Identification")
print("================================")

finger_present = False

while True:

    response = capture_finger()

    code = confirmation(response)

    # --------------------------------------------------------
    # Finger detected
    # --------------------------------------------------------

    if code == 0x00 and not finger_present:

        finger_present = True

        print()
        print("Finger detected")

        # Convert image
        response = image_to_character()

        if confirmation(response) != 0x00:

            print("Could not process fingerprint")

        else:

            # Search database
            response = search_finger()

            if response is None:

                print("No response from R307")

            else:

                code = confirmation(response)

                # --------------------------------------------
                # Match found
                # --------------------------------------------

                if code == 0x00 and len(response) >= 14:

                    page_id = (
                        response[10] << 8
                    ) | response[11]

                    score = (
                        response[12] << 8
                    ) | response[13]

                    print("------------------------")
                    print("MATCH FOUND")
                    print("Finger ID :", page_id)
                    print("Score     :", score)
                    print("------------------------")
                    
                    # Access granted
                    RED_LED.value(0)
                    GREEN_LED.value(1)

                    print("GREEN LED ON")

                    # Keep access indication ON for 60 seconds
                    time.sleep(10)

                    GREEN_LED.value(0)

                    print("GREEN LED OFF")

                # --------------------------------------------
                # No match
                # --------------------------------------------

                elif code == 0x09:

                    
                    print("------------------------")
                    print("UNKNOWN FINGERPRINT")
                    print("------------------------")
                    # Access denied
                    GREEN_LED.value(0)
                    RED_LED.value(1)

                    print("RED LED ON")

                    time.sleep(3)

                    RED_LED.value(0)

                    print("RED LED OFF")

                else:

                    print(
                        "Search error:",
                        hex(code) if code is not None else "None"
                    )

    # --------------------------------------------------------
    # Finger removed
    # --------------------------------------------------------

    elif code == 0x02:

        if finger_present:
            print("Finger removed")
            print()

        finger_present = False

    time.sleep_ms(300)