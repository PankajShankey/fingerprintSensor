from machine import UART, Pin
import time

uart = UART(
    2,
    baudrate=57600,
    bits=8,
    parity=None,
    stop=1,
    rx=Pin(14),
    tx=Pin(13)
)

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
        time.sleep_ms(5)


def get_template_count():

    # EF01 + address + PID + length + instruction + checksum
    packet = bytes([
        0xEF, 0x01,
        0xFF, 0xFF, 0xFF, 0xFF,
        0x01,
        0x00, 0x03,
        0x1D,
        0x00, 0x21
    ])

    clear_uart()

    print("TX:", " ".join("{:02X}".format(x) for x in packet))

    uart.write(packet)

    header = read_exact(9)

    if header is None:
        print("No response")
        return

    length = (header[7] << 8) | header[8]

    body = read_exact(length)

    if body is None:
        print("Incomplete response")
        return

    response = header + body

    print("RX:", " ".join("{:02X}".format(x) for x in response))

    confirmation = body[0]

    if confirmation != 0x00:
        print("Error:", hex(confirmation))
        return

    template_count = (body[1] << 8) | body[2]

    print("Templates stored:", template_count)


get_template_count()