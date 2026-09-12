from PIL import Image

RAW_FILE = "fingerprint.raw"
OUTPUT_FILE = "fingerprint.png"

WIDTH = 256
HEIGHT = 288

# R307 sends 4-bit grayscale:
# each byte contains 2 pixels
# high nibble = first pixel
# low nibble = second pixel

with open(RAW_FILE, "rb") as f:
    raw = f.read()

print("Raw bytes:", len(raw))

expected = WIDTH * HEIGHT // 2

if len(raw) != expected:
    print("ERROR: Expected", expected, "bytes")
    raise SystemExit

pixels = bytearray(WIDTH * HEIGHT)

p = 0

for byte in raw:

    high = (byte >> 4) & 0x0F
    low = byte & 0x0F

    # Convert 0..15 grayscale to 0..255
    pixels[p] = high * 17
    pixels[p + 1] = low * 17

    p += 2


image = Image.frombytes(
    "L",
    (WIDTH, HEIGHT),
    bytes(pixels)
)

image.save(OUTPUT_FILE)

print("Saved:", OUTPUT_FILE)