"""BlexShot — Windows screenshot editor entry point."""
import os
import sys

if __name__ == "__main__":
    # Set awareness before Qt or MSS creates a window/DC.
    from snapforge.platform import enable_dpi_awareness
    enable_dpi_awareness()
    from snapforge.app import run
    sys.exit(run(sys.argv))
