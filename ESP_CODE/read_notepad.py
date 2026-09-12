from machine import UART, Pin
import time

# --------------------------------------------------
# R307 UART
# R307 TX -> ESP32 GPIO14
# R307 RX -> ESP32 GPIO13
# --------------------------------------------------

uart = UART(
    2,
    baudrate=57600,
    bits=8,
    parity=None,
    stop=1,
    rx=Pin(14),
    tx=Pin(13)
)

HEADER = b'\xEF\x01'
ADDRESS = b'\xFF\xFF\xFF\xFF'


def read_exact(count, timeout_ms=2000):
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


def clear_uart():
    while uart.any():
        uart.read()
        time.sleep_ms(10)


def read_notepad(page):
    """
    Read one R307 notepad page.
    Valid pages: 0 to 15
    Each page: 32 bytes
    """

    if page < 0 or page > 15:
        print("Invalid page number. Use 0 to 15.")
        return None

    # --------------------------------------------------
    # Command:
    #
    # EF 01
    # FF FF FF FF
    # 01          Packet ID
    # 00 04       Packet length
    # 19          ReadNotepad instruction
    # XX          Page number
    # checksum H
    # checksum L
    # --------------------------------------------------

    packet_id = 0x01
    length_high = 0x00
    length_low = 0x04
    instruction = 0x19

    checksum = (
        packet_id
        + length_high
        + length_low
        + instruction
        + page
    )

    packet = bytearray([
        0xEF, 0x01,
        0xFF, 0xFF, 0xFF, 0xFF,
        packet_id,
        length_high, length_low,
        instruction,
        page,
        (checksum >> 8) & 0xFF,
        checksum & 0xFF
    ])

    clear_uart()

    print("\nReading Notepad Page:", page)
    print("TX:", " ".join("{:02X}".format(x) for x in packet))

    uart.write(packet)

    # First read:
    # Header 2 + Address 4 + PID 1 + Length 2 = 9 bytes
    header = read_exact(9)

    if header is None:
        print("ERROR: No response from R307")
        return None

    if header[0:2] != HEADER:
        print("ERROR: Invalid packet header")
        print("RX:", header)
        return None

    packet_id_rx = header[6]

    packet_length = (header[7] << 8) | header[8]

    # packet_length includes:
    # confirmation + data + checksum
    body = read_exact(packet_length)

    if body is None:
        print("ERROR: Incomplete response")
        return None

    full_response = header + body

    print(
        "RX:",
        " ".join("{:02X}".format(x) for x in full_response)
    )

    confirmation = body[0]

    if confirmation != 0x00:
        print(
            "ReadNotepad failed. Confirmation code:",
            hex(confirmation)
        )
        return None

    # body:
    # [confirmation]
    # [32 bytes user data]
    # [checksum high]
    # [checksum low]

    data = body[1:-2]

    print("Read successful")
    print("Bytes received:", len(data))

    return data


for page in range(16):

    data = read_notepad(page)

    if data is not None:

        print("\nPage", page)

        print("HEX:")
        print(" ".join("{:02X}".format(x) for x in data))

        text = ""

        for b in data:
            if 32 <= b <= 126:
                text += chr(b)
            else:
                text += "."

        print("ASCII:")
        print(text)

    time.sleep_ms(100)