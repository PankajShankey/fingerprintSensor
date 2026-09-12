from machine import UART, Pin
import time

# R307 TX -> ESP32 GPIO13
# R307 RX -> ESP32 GPIO14

uart = UART(
    2,
    baudrate=57600,
    bits=8,
    parity=None,
    stop=1,
    rx=Pin(14),
    tx=Pin(13)
)

time.sleep_ms(1000)

print("R307 - Clear Fingerprint Library")
print("--------------------------------")


# Empty Finger Library command
#
# EF 01          Header
# FF FF FF FF    Address
# 01             Command packet
# 00 03          Length
# 0D             Empty library instruction
# 00 11          Checksum

empty_command = bytes([
    0xEF, 0x01,
    0xFF, 0xFF, 0xFF, 0xFF,
    0x01,
    0x00, 0x03,
    0x0D,
    0x00, 0x11
])


# Clear UART buffer
while uart.any():
    uart.read()


print("Sending CLEAR command...")

uart.write(empty_command)

time.sleep_ms(500)


if uart.any():

    response = uart.read()

    print("Received:")
    print(response)

    print("HEX:")
    print(" ".join("{:02X}".format(x) for x in response))

    # Confirmation byte normally at position 9
    if len(response) >= 10:

        confirmation = response[9]

        if confirmation == 0x00:
            print("SUCCESS: Fingerprint library cleared.")

        elif confirmation == 0x13:
            print("FAILED: Module password is incorrect / authentication required.")

        elif confirmation == 0x11:
            print("FAILED: Could not clear fingerprint library.")

        else:
            print("Confirmation code:", hex(confirmation))

else:
    print("No response from R307")