"""PyInstaller entry point for the Windows desktop application."""

import sys

from novel_factory.desktop import main
from novel_factory.diagnostics import run_self_test


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        report = run_self_test()
        if sys.stdout is not None:
            print(report.to_json())
        raise SystemExit(0 if report.passed else 1)
    main()
