#!/usr/bin/env python3
import sys
import os
import re

# AutoPulse Security Red Line Scanner
# Mandate: Prevent write-access (UDS/J1979-2) to the vehicle ECU.

FORBIDDEN_PATTERNS = [
    r"0x05", # Request Vehicle Information (Request DTCs is OK, but we watch for high-level write)
    r"0x06", # Request onboard monitoring test results for specific monitored systems (Write variant)
    r"0x08", # Request control of on-board system, test or component
    r"0x0E", # WriteDataByIdentifier
    r"0x2E", # WriteDataByIdentifier (UDS)
    r"0x10", # DiagnosticSessionControl (specifically watching for non-default sessions)
    r"0x11", # ECUReset
    r"0x14", # ClearDiagnosticInformation
    r"0x27", # SecurityAccess (Write pre-req)
    r"0x28", # CommunicationControl
    r"0x31", # RoutineControl (can trigger write routines)
    r"0x34", # RequestDownload
    r"0x35", # RequestUpload
    r"0x36", # TransferData
    r"0x37", # RequestTransferExit
    r"0x3D", # WriteMemoryByAddress
]

def scan_file(file_path):
    violations = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f, 1):
                for pattern in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(f"Line {i}: Found forbidden pattern '{pattern}'")
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return violations

def main():
    root_dir = "src"
    all_violations = {}
    
    print(f"--- AutoPulse Red Line Scanner ---")
    print(f"Scanning directory: {root_dir}")
    
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith(('.py', '.json', '.sh')):
                path = os.path.join(root, file)
                violations = scan_file(path)
                if violations:
                    all_violations[path] = violations

    if all_violations:
        print("\n\033[91m[FAILURE] SECURITY RED LINES VIOLATED!\033[0m")
        for path, violations in all_violations.items():
            print(f"\nFile: {path}")
            for v in violations:
                print(f"  - {v}")
        sys.exit(1)
    else:
        print("\n\033[92m[PASS] No security red lines detected in 'src/'.\033[0m")
        sys.exit(0)

if __name__ == "__main__":
    main()
