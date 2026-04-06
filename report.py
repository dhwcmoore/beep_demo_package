import json

with open("output/beep_output.json") as f:
    data = json.load(f)

print("\n==============================")
print("   BEEP BEFORE BANG REPORT")
print("==============================\n")

print(f"Risk Level: {data['risk_level']}")
print(f"Risk Score: {data['risk_score']}\n")

print("Signals:")
print(f"  Rupture Score   : {data['signals']['rupture_score']}")
print(f"  Invariant Score : {data['signals']['invariant_score']}\n")

print("Detected Structural Issues:")

inv = data["signals"]["invariants"]

seen = set()
for adv in inv["advisories"]:
    key = (adv["severity"], adv["code"])
    if key not in seen:
        seen.add(key)
        print(f"  - [{adv['severity']}] {adv['code']}")

print("\nInterpretation:")
print("  System shows both instability and structural failure.")
print("  Early warning triggered BEFORE full operational breakdown.\n")
