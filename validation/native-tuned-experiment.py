"""Build the next native candidate from the delivered preview's exact source."""
from pathlib import Path
import shutil
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('--name',default='native-tuned')
args=parser.parse_args()
if not args.name.replace('-','').isalnum():
    parser.error('name must contain only letters, digits and hyphens')

root=Path(__file__).resolve().parent.parent
source=root/'validation/baselines/preview-2026-10-17-0803/Source'
out=root/'validation/experiments'/args.name
out.mkdir(exist_ok=True)
for name in ('src','tests'):
    shutil.copytree(source/name,out/name,dirs_exist_ok=True)
shutil.copy2(source/'CMakeLists.txt',out/'CMakeLists.txt')
shutil.copy2(root/'validation/experiments/field-unroll-2/fractal.hlsl',out/'src/fractal.hlsl')
print(out)
