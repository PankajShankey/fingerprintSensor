from machine import UART, Pin
import time


# ============================================================
# R307 + ESP32 CONFIGURATION
# ============================================================

uart = UART(
    2,
    baudrate=57600,
    bits=8,
    parity=None,
    stop=1,
    tx=Pin(13),       # ESP32 TX -> R307 RX
    rx=Pin(14),       # ESP32 RX <- R307 TX
    timeout=1000
)

ADDRESS = bytes([0xFF, 0xFF, 0xFF, 0xFF])


# ============================================================
# CHECKSUM
# ============================================================

def checksum(data):
    return sum(data) & 0xFFFF


# ============================================================
# CREATE R307 COMMAND PACKET
# ============================================================

def make_command(instruction, parameters=b''):

    content = bytes([instruction]) + parameters

    # Length = instruction/parameters + checksum(2 bytes)
    length = len(content) + 2

    packet = (
        bytes([0xEF, 0x01]) +
        ADDRESS +
        bytes([0x01]) +
        length.to_bytes(2, 'big') +
        content
    )

    cs = checksum(packet[6:])

    packet += cs.to_bytes(2, 'big')

    return packet


# ============================================================
# SEND COMMAND
# ============================================================

def send_command(instruction, parameters=b'', delay=300):

    # Remove old data
    while uart.any():
        uart.read()

    command = make_command(instruction, parameters)

    uart.write(command)

    time.sleep_ms(delay)

    response = uart.read()

    return response


# ============================================================
# DISPLAY RESPONSE
# ============================================================

def print_response(response):

    if not response:
        print("No response from sensor")
        return None

    print("RX:")
    print(response)

    print("HEX:")
    print(" ".join("{:02X}".format(x) for x in response))

    if len(response) >= 10:
        confirmation = response[9]

        print("Confirmation Code: {:02X}".format(confirmation))

        return confirmation

    return None


# ============================================================
# ERROR MESSAGE
# ============================================================

def error_message(code):

    errors = {
        0x00: "OK",
        0x01: "Error receiving packet",
        0x02: "No finger detected",
        0x03: "Failed to enroll fingerprint",
        0x06: "Failed to generate character file",
        0x07: "Failed to combine character files",
        0x08: "Invalid fingerprint image",
        0x09: "Failed to search fingerprint",
        0x0A: "Failed to match fingerprint",
        0x0B: "Failed to find matching fingerprint",
        0x0C: "Failed to combine fingerprint",
        0x10: "Flash memory write error",
        0x18: "Error during communication",
        0x19: "Password error",
        0x1D: "Template database error",
        0x1E: "Template not found",
        0x20: "Address error",
        0x21: "Password error",
        0xFF: "Unknown error"
    }

    return errors.get(code, "Unknown error")


# ============================================================
# GEN IMG - CAPTURE FINGER IMAGE
# ============================================================

def gen_img():

    response = send_command(0x01, delay=300)

    if not response:
        print("Sensor communication error")
        return False

    if len(response) < 10:
        print("Invalid response")
        return False

    code = response[9]

    if code == 0x00:
        return True

    elif code == 0x02:
        return False

    else:
        print("GenImg Error: {:02X} - {}".format(
            code,
            error_message(code)
        ))

        return False


# ============================================================
# WAIT FOR FINGER
# ============================================================

def wait_for_finger():

    print()
    print("Place your finger on the sensor...")

    while True:

        response = send_command(0x01, delay=150)

        if response and len(response) >= 10:

            code = response[9]

            if code == 0x00:
                print("Finger detected!")
                return True

            elif code == 0x02:
                pass

            else:
                print(
                    "Sensor error: {:02X} - {}".format(
                        code,
                        error_message(code)
                    )
                )
                return False

        time.sleep_ms(200)


# ============================================================
# WAIT FOR FINGER REMOVAL
# ============================================================

def wait_for_finger_removed():

    print()
    print("Remove your finger...")

    while True:

        response = send_command(0x01, delay=150)

        if response and len(response) >= 10:

            code = response[9]

            if code == 0x02:
                print("Finger removed.")
                return True

            elif code == 0x00:
                pass

            else:
                print(
                    "Sensor error: {:02X} - {}".format(
                        code,
                        error_message(code)
                    )
                )
                return False

        time.sleep_ms(200)


# ============================================================
# IMG2TZ - CONVERT IMAGE TO CHARACTER FILE
# ============================================================

def image_to_character(buffer_id):

    print(
        "Converting image to character file "
        "(Buffer {})...".format(buffer_id)
    )

    response = send_command(
        0x02,
        bytes([buffer_id]),
        delay=500
    )

    if not response:
        print("Sensor communication error")
        return False

    code = response[9]

    if code == 0x00:
        print("Character file generated successfully.")
        return True

    print(
        "Img2Tz Error: {:02X} - {}".format(
            code,
            error_message(code)
        )
    )

    return False


# ============================================================
# REG MODEL - COMBINE TWO CHARACTER FILES
# ============================================================

def create_model():

    print("Combining fingerprint data...")

    response = send_command(
        0x05,
        delay=500
    )

    if not response:
        print("Sensor communication error")
        return False

    code = response[9]

    if code == 0x00:
        print("Fingerprint model created successfully.")
        return True

    print(
        "RegModel Error: {:02X} - {}".format(
            code,
            error_message(code)
        )
    )

    return False


# ============================================================
# STORE - SAVE TEMPLATE
# ============================================================

def store_fingerprint(finger_id):

    high = (finger_id >> 8) & 0xFF
    low = finger_id & 0xFF

    parameters = bytes([
        0x01,       # Buffer ID
        high,
        low
    ])

    print("Storing fingerprint at ID {}...".format(finger_id))

    response = send_command(
        0x06,
        parameters,
        delay=500
    )

    if not response:
        print("Sensor communication error")
        return False

    code = response[9]

    if code == 0x00:
        print()
        print("================================")
        print(" Finger enrolled successfully!")
        print(" Finger ID:", finger_id)
        print("================================")
        return True

    print(
        "Store Error: {:02X} - {}".format(
            code,
            error_message(code)
        )
    )

    return False


# ============================================================
# ENROLL
# ============================================================

def enroll():

    print()
    print("==============================")
    print("       ENROLL FINGER")
    print("==============================")

    try:
        finger_id = int(input("Enter Finger ID (0-999): "))

    except:
        print("Invalid ID.")
        return

    if finger_id < 0 or finger_id > 999:
        print("ID must be between 0 and 999.")
        return

    print()
    print("STEP 1")
    print("Put your finger on sensor.")

    if not wait_for_finger():
        return

    # Capture first image
    print("Capturing first fingerprint image...")

    if not image_to_character(1):
        return

    # Remove finger
    if not wait_for_finger_removed():
        return

    print()
    print("STEP 2")
    print("Put the SAME finger again.")

    if not wait_for_finger():
        return

    # Capture second image
    print("Capturing second fingerprint image...")

    if not image_to_character(2):
        return

    # Remove finger
    wait_for_finger_removed()

    # Combine
    if not create_model():
        return

    # Store
    store_fingerprint(finger_id)


# ============================================================
# SEARCH / IDENTIFY
# ============================================================

def identify():

    print()
    print("==============================")
    print("      IDENTIFY FINGER")
    print("==============================")

    if not wait_for_finger():
        return

    print("Converting fingerprint...")

    if not image_to_character(1):
        return

    print("Searching fingerprint database...")

    # Buffer 1
    # Start Page = 0
    # Page Number = 1000
    parameters = bytes([
        0x01,
        0x00, 0x00,
        0x03, 0xE8
    ])

    response = send_command(
        0x04,
        parameters,
        delay=700
    )

    if not response:
        print("Sensor communication error")
        return

    print_response(response)

    if len(response) < 14:
        print("Invalid search response.")
        return

    code = response[9]

    if code == 0x00:

        page_id = (response[10] << 8) | response[11]

        match_score = (response[12] << 8) | response[13]

        print()
        print("================================")
        print("       FINGER MATCHED")
        print("================================")
        print("Finger ID   :", page_id)
        print("Match Score :", match_score)
        print("================================")

    elif code == 0x09:

        print()
        print("No matching fingerprint found.")

    else:

        print(
            "Search Error: {:02X} - {}".format(
                code,
                error_message(code)
            )
        )


# ============================================================
# DELETE FINGER
# ============================================================

def delete_finger():

    print()
    print("==============================")
    print("       DELETE FINGER")
    print("==============================")

    try:
        finger_id = int(input("Enter Finger ID (0-999): "))

    except:
        print("Invalid ID.")
        return

    if finger_id < 0 or finger_id > 999:
        print("ID must be between 0 and 999.")
        return

    high = (finger_id >> 8) & 0xFF
    low = finger_id & 0xFF

    parameters = bytes([
        high,
        low,
        0x00,
        0x01
    ])

    print("Deleting ID {}...".format(finger_id))

    response = send_command(
        0x0C,
        parameters,
        delay=500
    )

    if not response:
        print("Sensor communication error")
        return

    code = response[9]

    if code == 0x00:
        print("Fingerprint ID {} deleted.".format(finger_id))

    else:
        print(
            "Delete Error: {:02X} - {}".format(
                code,
                error_message(code)
            )
        )


# ============================================================
# FINGER COUNT
# ============================================================

def finger_count():

    print()
    print("==============================")
    print("       FINGER COUNT")
    print("==============================")

    response = send_command(
        0x1D,
        delay=500
    )

    if not response:
        print("Sensor communication error")
        return

    print_response(response)

    if len(response) >= 12:

        code = response[9]

        if code == 0x00:

            count = (response[10] << 8) | response[11]

            print()
            print("Total enrolled fingerprints:", count)


# ============================================================
# CLEAR DATABASE
# ============================================================

def clear_database():

    print()
    print("==============================")
    print("       CLEAR DATABASE")
    print("==============================")

    confirm = input(
        "Delete ALL fingerprints? (yes/no): "
    )

    if confirm.lower() != "yes":
        print("Cancelled.")
        return

    response = send_command(
        0x0D,
        delay=700
    )

    if not response:
        print("Sensor communication error")
        return

    code = response[9]

    if code == 0x00:
        print("All fingerprints deleted.")

    else:
        print(
            "Clear Error: {:02X} - {}".format(
                code,
                error_message(code)
            )
        )


# ============================================================
# MAIN MENU
# ============================================================

print()
print("================================")
print("       R307 FINGERPRINT")
print("================================")

while True:

    print()
    print("1. Enroll Finger")
    print("2. Identify Finger")
    print("3. Delete Finger")
    print("4. Finger Count")
    print("5. Clear Database")
    print("6. Exit")
    print("================================")

    choice = input("Select option: ")

    if choice == "1":

        enroll()

    elif choice == "2":

        identify()

    elif choice == "3":

        delete_finger()

    elif choice == "4":

        finger_count()

    elif choice == "5":

        clear_database()

    elif choice == "6":

        print("Exiting...")
        break

    else:

        print("Invalid option.")