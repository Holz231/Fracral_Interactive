"""Compare temporal reconstruction against native eight-sample reference images.

Run from the repository root. Both variants use the same executable, camera,
simulation steps, resolution and jitter. AURORA_TAA_DETAIL selects the filter.
"""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw


def luminance(image):
    return image @ np.array([.2126, .7152, .0722], dtype=np.float32)


def gradients(image):
    y = luminance(image)
    return np.diff(y, axis=1), np.diff(y, axis=0)


def metrics(image, reference):
    error = image - reference
    gx, gy = gradients(image)
    rx, ry = gradients(reference)
    energy = np.mean(np.abs(gx)) + np.mean(np.abs(gy))
    ref_energy = np.mean(np.abs(rx)) + np.mean(np.abs(ry))
    return dict(psnr=float(10*np.log10(255**2/max(float(np.mean(error**2)), 1e-12))),
                mae=float(np.mean(np.abs(error))), edge_ratio=float(energy/max(ref_energy, 1e-12)),
                gradient_error=float((np.mean(np.abs(gx-rx))+np.mean(np.abs(gy-ry)))/2))


def compare(root):
    root = Path(root)
    records = []
    for before in sorted(root.glob('before-*')):
        after = root / before.name.replace('before-', 'after-', 1)
        if not after.exists():
            continue
        meta = json.loads((before/'reference.json').read_text())
        w, h = meta['width'], meta['height']
        for frame in sorted(before.glob('frame-*.png'), key=lambda p: int(p.stem.split('-')[1])):
            index = frame.stem.split('-')[1]
            raw = np.fromfile(before/f'reference-{index}.rgba', dtype=np.uint8).reshape(h, w, 4)
            other = np.fromfile(after/f'reference-{index}.rgba', dtype=np.uint8).reshape(h, w, 4)
            if not np.array_equal(raw, other):
                raise RuntimeError(f'Reference cameras or jitter differ: {before.name}, frame {index}')
            ref = raw[:, :, :3].astype(np.float32)
            for variant, folder in [('before', before), ('after', after)]:
                im = np.asarray(Image.open(folder/frame.name).convert('RGB'), dtype=np.float32)
                records.append(dict(fixture=before.name[7:], frame=int(index), variant=variant, **metrics(im, ref)))
    if not records:
        raise RuntimeError('No matching before/after captures')
    with (root/'quality.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    summaries = {}
    for fixture in sorted({r['fixture'] for r in records}):
        summaries[fixture] = {}
        for variant in ['before', 'after']:
            subset = [r for r in records if r['fixture'] == fixture and r['variant'] == variant and r['frame'] > 0]
            timing = list(csv.DictReader((root/f'{variant}-{fixture}'/'flight.csv').open()))[8:]
            summaries[fixture][variant] = {key: float(np.mean([r[key] for r in subset])) for key in ['psnr', 'mae', 'edge_ratio', 'gradient_error']}
            summaries[fixture][variant].update(gpu_ms=float(np.median([float(r['gpu_ms']) for r in timing])),
                                               frame_change=float(np.mean([float(r['mean_change']) for r in timing])),
                                               steady_change=float(np.mean([float(r['mean_change']) for r in timing[-32:]])))
        b, a = summaries[fixture]['before'], summaries[fixture]['after']
        print(f"{fixture:26} PSNR {b['psnr']:.2f}->{a['psnr']:.2f} dB | edges {b['edge_ratio']:.3f}->{a['edge_ratio']:.3f} | grad error {b['gradient_error']:.3f}->{a['gradient_error']:.3f} | GPU {b['gpu_ms']:.2f}->{a['gpu_ms']:.2f} ms", flush=True)
    (root/'summary.json').write_text(json.dumps(summaries, indent=2))
    return summaries


def preview(root, fixture):
    root = Path(root); before = root/f'before-{fixture}'; after = root/f'after-{fixture}'
    meta = json.loads((before/'reference.json').read_text()); w, h = meta['width'], meta['height']
    frames = sorted(before.glob('frame-*.png'), key=lambda p: int(p.stem.split('-')[1])); last = frames[-1]
    index = last.stem.split('-')[1]
    ref = np.fromfile(before/f'reference-{index}.rgba', dtype=np.uint8).reshape(h, w, 4)
    images = [Image.open(before/last.name).convert('RGB'), Image.open(after/last.name).convert('RGB'), Image.fromarray(ref[:, :, :3])]
    crop = (w//2-192, h//2-192, w//2+192, h//2+192)
    sheet = Image.new('RGB', (384*3, 424), '#161a20'); draw = ImageDraw.Draw(sheet)
    for column, (im, title) in enumerate(zip(images, ['Before', 'Sharper temporal filter', 'Native 8-sample reference'])):
        sheet.paste(im.crop(crop), (column*384, 40)); draw.text((column*384+12, 12), title, fill='white')
    sheet.save(root/f'comparison-{fixture}.png')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('exe'); p.add_argument('output')
    p.add_argument('--fixtures', default='corner,interior,user-root-slow')
    p.add_argument('--size', default='1920x1080'); p.add_argument('--frames', type=int, default=90)
    p.add_argument('--speed', type=float, default=3.8); p.add_argument('--turn', type=float, default=0)
    p.add_argument('--quality', type=int, default=1); p.add_argument('--every', type=int, default=30)
    p.add_argument('--compare-only', action='store_true')
    p.add_argument('--preview')
    p.add_argument('--env', action='append', default=[])
    args = p.parse_args()
    root = Path(args.output).resolve(); root.mkdir(parents=True, exist_ok=True)
    if args.compare_only:
        compare(root)
        if args.preview: preview(root, args.preview)
        return
    exe = Path(args.exe).resolve(); w, h = args.size.split('x')
    fixtures = Path(__file__).resolve().parent.parent/'fixtures'
    for name in args.fixtures.split(','):
        fixture = Path(name).resolve() if name.endswith('.aurora') else fixtures/(name+'.aurora')
        for mode, variant in [('0', 'before'), ('1', 'after')]:
            out = root/f'{variant}-{fixture.stem}'; out.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update(AURORA_TAA_DETAIL=mode, AURORA_BENCH_QUALITY=str(args.quality), AURORA_DRS='0',
                       AURORA_FLY_DRS='0', AURORA_FLY_YAW=str(args.turn), AURORA_TAAU='1')
            env.update(dict(item.split('=', 1) for item in args.env))
            started = time.monotonic()
            completed = subprocess.run([str(exe), '--temporal-audit', str(out), w, h, str(args.frames),
                                        str(args.speed), str(args.every), str(fixture)], cwd=out, env=env)
            if completed.returncode:
                error = out/'aurora-error.txt'
                raise RuntimeError(error.read_text() if error.exists() else str(completed.returncode))
            print(f'{variant} {fixture.stem}: {time.monotonic()-started:.1f}s', flush=True)
    compare(root)
    if args.preview: preview(root, args.preview)


if __name__ == '__main__':
    main()
