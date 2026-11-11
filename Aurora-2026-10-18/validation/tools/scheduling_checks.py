"""Check empty-queue preparation with real GPU colour and depth readbacks."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np


def digest(path):
    with Path(path).open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def run(exe, output, mode, quality, fixtures, temporal, diagnostic=False):
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(AURORA_EMPTY_SCAN=mode, AURORA_BENCH_QUALITY=str(quality),
               AURORA_TEMPORAL=str(int(temporal)), AURORA_DRS='0', AURORA_TAA_DETAIL='1',
               AURORA_SHADER_FILE='', AURORA_SHADER_DEFINES='TRACE_STATS=1' if diagnostic else '')
    size = ['1980', '1058'] if diagnostic else ['3840', '2160']
    args = [str(exe), '--diag-views' if diagnostic else '--bench-views', str(output), *size]
    if not diagnostic:
        args += ['16']
    result = subprocess.run(args + [str(p) for p in fixtures], cwd=output, env=env)
    if result.returncode:
        error = output/'aurora-error.txt'
        raise RuntimeError(error.read_text() if error.exists() else f'GPU check exited {result.returncode}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe'); parser.add_argument('output')
    parser.add_argument('--extra', action='append', default=[])
    args = parser.parse_args()
    exe = Path(args.exe).resolve(); output = Path(args.output).resolve()
    fixture_dir = Path(__file__).resolve().parent.parent/'fixtures'
    all_fixtures = sorted(fixture_dir.glob('*.aurora')) + [Path(p).resolve() for p in args.extra]
    heavy = [fixture_dir/(n+'.aurora') for n in ['corner', 'heavy69', 'slow45', 'user-root-slow', 'user-preview0817-slow']]
    scenarios = [('balanced-4k', 1, all_fixtures),
                 ('ultra-4k', 2, heavy + [Path(p).resolve() for p in args.extra]),
                 ('performance-4k', 0, heavy + [Path(p).resolve() for p in args.extra])]
    summary = {'executable_sha256': digest(exe), 'colours': {}, 'depths': {}}
    for name, quality, fixtures in scenarios:
        for mode, label in [('0', 'baseline'), ('1', 'optimized')]:
            print(f'{name}: {label}', flush=True)
            run(exe, output/f'{name}-{label}', mode, quality, fixtures, True)
        for fixture in fixtures:
            before = output/f'{name}-baseline'/(fixture.stem+'.png')
            after = output/f'{name}-optimized'/(fixture.stem+'.png')
            if digest(before) != digest(after):
                raise RuntimeError(f'Colour changed: {name}, {fixture.stem}')
        for label in ['baseline', 'optimized']:
            rows = list(csv.DictReader((output/f'{name}-{label}'/'bench.csv').open()))
            if len(rows) != len(fixtures) or any(int(row['unfinished']) for row in rows):
                raise RuntimeError(f'Incomplete rays: {name}, {label}')
        summary['colours'][name] = len(fixtures)
        print(f'{name}: {len(fixtures)} identical PNGs, zero unfinished pixels', flush=True)

    # Diagnostics retain each pixel's exact logarithmic hit depth and status.
    depth_fixtures = [fixture_dir/(n+'.aurora') for n in ['heavy69', 'slow41', 'slow45', 'user-root-slow']]
    for mode, label in [('0', 'baseline'), ('1', 'optimized')]:
        print(f'depth readback: {label}', flush=True)
        run(exe, output/f'depth-{label}', mode, 1, depth_fixtures, False, True)
    for fixture in depth_fixtures:
        before = output/'depth-baseline'/(fixture.stem+'-rays.bin')
        after = output/'depth-optimized'/(fixture.stem+'-rays.bin')
        if digest(before) != digest(after):
            raise RuntimeError(f'Hit depth or classification changed: {fixture.stem}')
        rays = np.fromfile(after, dtype=np.float32).reshape(-1, 2)
        if not np.isfinite(rays).all() or np.any(rays[:, 1] < 0):
            raise RuntimeError(f'Invalid or unfinished rays: {fixture.stem}')
        summary['depths'][fixture.stem] = len(rays)
    (output/'summary.json').write_text(json.dumps(summary, indent=2))
    print(f"PASS: {sum(summary['colours'].values())} identical 4K images; "
          f"{sum(summary['depths'].values())} identical ray depths/statuses", flush=True)


if __name__ == '__main__':
    main()
