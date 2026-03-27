"""
Parse JUnit XML test results and print a formatted endpoint test report.

Usage: python tests/generate_report.py test-results.xml
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

# Map test file names to router/endpoint groups
FILE_TO_GROUP = {
    "test_health": "Health",
    "test_auth": "Auth (/auth)",
    "test_clinics": "Clinics (/clinics)",
    "test_patients": "Patients (/patients)",
    "test_simulations": "Simulations (/simulations)",
    "test_images": "Images (/images)",
    "test_consent": "Consent (/consent)",
    "test_post_procedure": "Post-Procedure (/post-procedure)",
    "test_share": "Share (/share)",
    "test_team": "Team (/team)",
    "test_admin": "Admin (/admin)",
    "test_audit_logs": "Audit Logs (/audit-logs)",
    "test_subscription": "Subscription (/subscription)",
    "test_image_validator": "Image Validator (service)",
}

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[36m"


def parse_results(xml_path: str):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    groups = defaultdict(list)
    total_pass = 0
    total_fail = 0
    total_error = 0
    total_skip = 0

    for suite in root.iter("testsuite"):
        for case in suite.iter("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            time_s = float(case.get("time", "0"))

            # Determine group from classname (e.g. "tests.test_auth")
            parts = classname.split(".")
            file_key = parts[-1] if parts else "unknown"
            group = FILE_TO_GROUP.get(file_key, file_key)

            # Determine status
            failure = case.find("failure")
            error = case.find("error")
            skipped = case.find("skipped")

            if failure is not None:
                status = "FAIL"
                detail = failure.get("message", "")[:120]
                total_fail += 1
            elif error is not None:
                status = "ERROR"
                detail = error.get("message", "")[:120]
                total_error += 1
            elif skipped is not None:
                status = "SKIP"
                detail = skipped.get("message", "")[:120]
                total_skip += 1
            else:
                status = "PASS"
                detail = ""
                total_pass += 1

            # Clean up test name for display
            display_name = name.replace("test_", "").replace("_", " ").title()

            groups[group].append({
                "name": display_name,
                "raw_name": name,
                "status": status,
                "time": time_s,
                "detail": detail,
            })

    return groups, total_pass, total_fail, total_error, total_skip


def print_report(groups, total_pass, total_fail, total_error, total_skip):
    total = total_pass + total_fail + total_error + total_skip
    line = "=" * 80

    print(f"\n{BOLD}{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}  SMILEPREVIEW API -- ENDPOINT TEST REPORT{RESET}")
    print(f"{BOLD}{CYAN}{line}{RESET}\n")

    # Sort groups by the order in FILE_TO_GROUP
    ordered_groups = list(FILE_TO_GROUP.values())

    for group_name in ordered_groups:
        if group_name not in groups:
            continue
        tests = groups[group_name]

        group_passed = sum(1 for t in tests if t["status"] == "PASS")
        group_total = len(tests)
        group_color = GREEN if group_passed == group_total else RED

        print(f"{BOLD}  {group_name}  {group_color}({group_passed}/{group_total} passed){RESET}")
        print(f"  {'-' * 76}")

        for t in tests:
            if t["status"] == "PASS":
                icon = f"{GREEN}PASS{RESET}"
            elif t["status"] == "FAIL":
                icon = f"{RED}FAIL{RESET}"
            elif t["status"] == "ERROR":
                icon = f"{RED}ERR {RESET}"
            else:
                icon = f"{YELLOW}SKIP{RESET}"

            time_str = f"{DIM}{t['time']:.2f}s{RESET}"
            print(f"    [{icon}] {t['name']:<55} {time_str}")
            if t["detail"]:
                print(f"           {DIM}{t['detail']}{RESET}")

        print()

    # Print any groups not in FILE_TO_GROUP
    for group_name, tests in groups.items():
        if group_name in ordered_groups:
            continue
        group_passed = sum(1 for t in tests if t["status"] == "PASS")
        group_total = len(tests)
        group_color = GREEN if group_passed == group_total else RED

        print(f"{BOLD}  {group_name}  {group_color}({group_passed}/{group_total} passed){RESET}")
        print(f"  {'-' * 76}")
        for t in tests:
            if t["status"] == "PASS":
                icon = f"{GREEN}PASS{RESET}"
            elif t["status"] == "FAIL":
                icon = f"{RED}FAIL{RESET}"
            else:
                icon = f"{YELLOW}SKIP{RESET}"
            time_str = f"{DIM}{t['time']:.2f}s{RESET}"
            print(f"    [{icon}] {t['name']:<55} {time_str}")
            if t["detail"]:
                print(f"           {DIM}{t['detail']}{RESET}")
        print()

    # Summary
    print(f"{BOLD}{CYAN}{line}{RESET}")
    pass_str = f"{GREEN}{BOLD}{total_pass} passed{RESET}"
    fail_str = f"{RED}{BOLD}{total_fail} failed{RESET}" if total_fail else f"{DIM}0 failed{RESET}"
    err_str = f"{RED}{BOLD}{total_error} errors{RESET}" if total_error else f"{DIM}0 errors{RESET}"
    skip_str = f"{YELLOW}{total_skip} skipped{RESET}" if total_skip else f"{DIM}0 skipped{RESET}"

    print(f"  {BOLD}TOTAL: {total} tests{RESET}  |  {pass_str}  |  {fail_str}  |  {err_str}  |  {skip_str}")

    if total_fail == 0 and total_error == 0:
        print(f"\n  {GREEN}{BOLD}ALL TESTS PASSED -- Ready to deploy.{RESET}")
    else:
        print(f"\n  {RED}{BOLD}FAILURES DETECTED -- Fix before deploying.{RESET}")

    print(f"{BOLD}{CYAN}{line}{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/generate_report.py <test-results.xml>")
        sys.exit(1)

    xml_path = sys.argv[1]
    groups, p, f, e, s = parse_results(xml_path)
    print_report(groups, p, f, e, s)
