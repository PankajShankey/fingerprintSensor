from machine import UART, Pin
import time

# ------------------------------------------------
# R307 UART
# R307 TXD -> ESP32 GPIO13 (RX)
# R307 RXD -> ESP32 GPIO14 (TX)
# ------------------------------------------------

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

print("R307 communication test")
print("-----------------------")


# ------------------------------------------------
# Verify Password command
#
# Header      = EF 01
# Address     = FF FF FF FF
# Packet ID   = 01
# Length      = 00 07
# Instruction = 13
# Password    = FF FF FF FF
# Checksum    = 04 17
# ------------------------------------------------

verify_command = bytes([
    0xEF, 0x01,
    0xFF, 0xFF, 0xFF, 0xFF,
    0x01,
    0x00, 0x07,
    0x13,
    0xFF, 0xFF, 0xFF, 0xFF,
    0x04, 0x17
])


# Clear old UART data
while uart.any():
    uart.read()


print("Sending Verify Password command...")

uart.write(verify_command)

time.sleep_ms(500)


# ------------------------------------------------
# Read R307 response
# ------------------------------------------------

if uart.any():

    response = uart.read()

    print("Received bytes:")
    print(response)

    print("HEX response:")
    print(" ".join("{:02X}".format(x) for x in response))

else:

    print("No response from R307")
