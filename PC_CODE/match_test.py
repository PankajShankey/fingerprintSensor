from afis import MindtctExtractor, SafisExtractor

ENROLLED_IMAGE = "hussain_1.png"
#TEST_IMAGE = "hussain_2.png"
TEST_IMAGE = "other_fingure.png"



print("Loading fingerprint matcher...")

# Extract minutiae using pure-Python MINDTCT
extractor = MindtctExtractor()

print("Extracting enrollment fingerprint...")
template1 = extractor.extract_minutiae(ENROLLED_IMAGE)

print("Extracting test fingerprint...")
template2 = extractor.extract_minutiae(TEST_IMAGE)

print()
print("============================")
print("MINUTIAE INFORMATION")
print("============================")

print("Enrollment minutiae:", template1.n_minutiae)
print("Test minutiae      :", template2.n_minutiae)


# SAFIS matcher
matcher = SafisExtractor()

print()
print("============================")
print("MATCHING")
print("============================")

result = matcher.match(template1, template2)

print("Match result:", result)