"""Compila con herramientas locales y credenciales de ejemplo; no carga la placa."""
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache/arduino'
cli = CACHE / 'bin/arduino-cli'
if not cli.exists():
    raise SystemExit('Prepara Arduino CLI según docs/firmware-y-protocolo.md.')
sketch = CACHE / 'sketch/leov1'
sketch.mkdir(parents=True, exist_ok=True)
for name in ('leov1.ino', 'transport.h'):
    shutil.copyfile(ROOT / 'firmware/leov1' / name, sketch / name)
shutil.copyfile(ROOT / 'firmware/leov1/config.example.h', sketch / 'config.h')
command = [str(cli), '--config-file', str(CACHE / 'arduino-cli.yaml'), 'compile',
           '--fqbn', 'esp32:esp32:esp32', '--build-path', str(CACHE / 'build')]
if (CACHE / 'ctags-source/ctags').exists():
    command += ['--build-property', 'runtime.tools.ctags.path=' + str(CACHE / 'ctags-source')]
subprocess.run(command + [str(sketch)], check=True)
