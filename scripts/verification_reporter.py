#!/usr/bin/env python3
import sys
import os
import json
import datetime
import subprocess

# AutoPulse Auditor-Ready Verification Reporter
# Goal: Consolidate Architect's intent, Dev's implementation, and QA results for the Lead Auditor.

def get_git_diff():
    try:
        return subprocess.check_output(["git", "diff", "HEAD~1", "HEAD"]).decode("utf-8")
    except:
        return "No recent git diff found."

def run_tests():
    try:
        result = subprocess.run(["python3", "-m", "pytest", "-q"], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Test execution failed: {e}"

def run_redline_scanner():
    try:
        result = subprocess.run(["python3", "scripts/redline_scanner.py"], capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        return f"Redline scanner failed: {e}"

def generate_report():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = f"docs/qa/verification_report_{timestamp}.md"
    
    # Check for CONTEXT.md to get active story
    story = "Unknown Story"
    if os.path.exists("autopulse/CONTEXT.md"):
        with open("autopulse/CONTEXT.md", "r") as f:
            content = f.read()
            if "Active Story:" in content:
                story = content.split("Active Story:")[1].split("\n")[0].strip()

    report_content = f"""# Auditor-Ready Verification Report
**Timestamp:** {timestamp}
**Active Story:** {story}

## 1. Architectural Intent
*Note: Refer to the Research Claims database and original PM Spec for baseline intent.*

## 2. Security Compliance (Red Lines)
```text
{run_redline_scanner()}
```

## 3. Implementation Evidence (Git Diff)
<details>
<summary>View Changes</summary>

```diff
{get_git_diff()}
```
</details>

## 4. QA Results (Local Test Run)
```text
{run_tests()}
```

## 5. Auditor Sign-off
- [ ] Logic aligns with Technical Spec
- [ ] No Security Red Lines violated
- [ ] 100% Test Pass Rate confirmed
"""
    
    os.makedirs("docs/qa", exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report_content)
    
    print(f"Verification report generated: {report_path}")

if __name__ == "__main__":
    generate_report()
