"""Verify the standalone executable with no Python/tool directories on PATH."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
exe = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else root / "dist" / "BlexShot.exe"
env = dict(os.environ)
windows = Path(env.get("SystemRoot", r"C:\Windows"))
env["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_DEBUG_PLUGINS", "QT_QPA_PLATFORM", "QT_PLUGIN_PATH"):
    env.pop(key, None)
try:
    with tempfile.TemporaryDirectory(prefix="snapforge-package-") as test_data:
        # An existing user instance must not satisfy or block this smoke test.
        env["LOCALAPPDATA"] = test_data
        result = subprocess.run([str(exe), "--smoke-test"], cwd=exe.parent, env=env, capture_output=True,
                                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
except subprocess.TimeoutExpired:
    sys.exit("Paket açılış testi 30 saniyede tamamlanamadı.")
if result.returncode:
    sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
    sys.exit(result.returncode)
payload = exe.read_bytes()
pe = struct.unpack_from("<I", payload, 0x3C)[0]
assert struct.unpack_from("<H", payload, pe + 4)[0] == 0x8664, "Not x64"
assert struct.unpack_from("<H", payload, pe + 24 + 68)[0] == 2, "Not Windows GUI subsystem"
report = {"executable": str(exe), "exit_code": result.returncode, "size_mb": round(len(payload) / 1024**2, 1),
          "sha256": hashlib.sha256(payload).hexdigest(), "isolated_path": True, "x64_gui": True}
output = root / "artifacts"
output.mkdir(exist_ok=True)
(output / "exe-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
