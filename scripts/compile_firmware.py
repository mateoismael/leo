"""Compile with local tooling and example credentials; never flashes the board."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/arduino'
cli = CACHE / 'bin/arduino-cli'
if not cli.exists():
    raise SystemExit('Set up Arduino CLI as described in docs/firmware-and-protocol.md.')
sketch = CACHE / 'sketch/wristband'
sketch.mkdir(parents=True, exist_ok=True)
for name in ('wristband.ino', 'transport.h'):
    shutil.copyfile(ROOT / 'firmware/wristband' / name, sketch / name)
shutil.copyfile(ROOT / 'firmware/wristband/config.example.h', sketch / 'config.h')
command = [str(cli), '--config-file', str(CACHE / 'arduino-cli.yaml'), 'compile',
           '--fqbn', 'esp32:esp32:esp32', '--build-path', str(CACHE / 'build')]
if (CACHE / 'ctags-source/ctags').exists():
    command += ['--build-property', 'runtime.tools.ctags.path=' + str(CACHE / 'ctags-source')]
subprocess.run(command + [str(sketch)], check=True)
