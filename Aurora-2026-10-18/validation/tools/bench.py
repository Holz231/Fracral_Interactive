"""Run AuroraFractal --bench-views for a build/variant and compare against a reference run.

usage: python bench.py <exe> <out-name> [--size 1980x1058] [--frames 24] [--ref results/baseline-1980]
                       [--env NAME=VALUE ...] [--fixtures a,b,c]
"""
import argparse, csv, os, subprocess, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(exe, out, size, frames, env_extra, fixtures, mode='--bench-views'):
    env = os.environ.copy()
    env.update(env_extra)
    w, h = size.split('x')
    args = [exe, mode, out, w, h] + ([str(frames)] if mode == '--bench-views' else []) + fixtures
    err = os.path.join(os.path.dirname(exe), 'aurora-error.txt')
    if os.path.exists(err):
        os.remove(err)
    r = subprocess.run(args, cwd=os.path.dirname(exe), env=env)
    if r.returncode != 0:
        msg = open(err, encoding='utf-8', errors='replace').read() if os.path.exists(err) else ''
        raise SystemExit(f'run failed ({r.returncode}): {msg}')


def compare(a_path, b_path):
    a = np.asarray(Image.open(a_path).convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(b_path).convert('RGB'), dtype=np.int16)
    d = np.abs(a - b).max(axis=2)
    return d.mean(), int((d > 16).sum()), int((d > 48).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('name')
    ap.add_argument('--size', default='1980x1058')
    ap.add_argument('--frames', type=int, default=24)
    ap.add_argument('--ref', default=os.path.join(ROOT, 'results', 'baseline-1980'))
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--fixtures', default='')
    a = ap.parse_args()
    env = dict(e.split('=', 1) for e in a.env)
    fx_dir = os.path.join(ROOT, 'fixtures')
    names = a.fixtures.split(',') if a.fixtures else sorted(f[:-7] for f in os.listdir(fx_dir) if f.endswith('.aurora'))
    fixtures = [os.path.join(fx_dir, n + '.aurora') for n in names]
    out = os.path.join(ROOT, 'results', a.name)
    run(os.path.abspath(a.exe), out, a.size, a.frames, env, fixtures)
    ref = {}
    ref_csv = os.path.join(a.ref, 'bench.csv')
    if os.path.exists(ref_csv):
        ref = {r['fixture']: r for r in csv.DictReader(open(ref_csv))}
    rows = list(csv.DictReader(open(os.path.join(out, 'bench.csv'))))
    print(f"{'fixture':24s} {'ms':>7s} {'ref':>7s} {'ratio':>6s} {'unfin':>6s} {'meanDiff':>8s} {'px>16':>7s} {'px>48':>7s}")
    tot = tot_ref = 0
    for r in rows:
        n = r['fixture']
        ms = float(r['median_ms'])
        rr = ref.get(n)
        rms = float(rr['median_ms']) if rr else float('nan')
        md = p16 = p48 = float('nan')
        rp = os.path.join(a.ref, n + '.png')
        if os.path.exists(rp):
            md, p16, p48 = compare(rp, os.path.join(out, n + '.png'))
        tot += ms
        tot_ref += rms
        print(f"{n:24s} {ms:7.2f} {rms:7.2f} {ms / rms:6.3f} {r['unfinished']:>6s} {md:8.3f} {p16:7} {p48:7}")
    print(f"{'TOTAL':24s} {tot:7.2f} {tot_ref:7.2f} {tot / tot_ref:6.3f}")


if __name__ == '__main__':
    main()
