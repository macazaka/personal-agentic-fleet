"""
CI Test Runner & Annotation Generator for Personal Agentic Fleet.
Executes pytest and outputs concise GitHub Actions error annotations on failure.
"""
import os
import subprocess
import sys


def main():
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    try:
        with open("pytest_log.txt", "w", encoding="utf-8") as f:
            f.write(res.stdout + "\n" + res.stderr)
    except Exception:
        pass

    if res.returncode != 0:
        failures = [
            line for line in (res.stdout + "\n" + res.stderr).splitlines()
            if line.startswith("FAILED") or line.startswith("ERROR")
        ]
        for line in failures[:5]:
            clean = line.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error::{clean}", file=sys.stderr)

        sf = os.getenv("GITHUB_STEP_SUMMARY")
        if sf:
            try:
                with open(sf, "a", encoding="utf-8") as f:
                    f.write(f"### Pytest Run Failure ({sys.platform})\n```\n{res.stdout[-3000:]}\n{res.stderr[-1000:]}\n```\n")
            except Exception:
                pass

    sys.exit(res.returncode)


if __name__ == "__main__":
    main()
