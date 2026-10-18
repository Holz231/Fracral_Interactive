"""Interleaved A/B(/C...) timing of renderer variants under identical conditions.

usage: python ab.py --variant NAME=EXE[;ENV=VAL;ENV2=VAL] ... [--rounds 3] [--fixtures a,b] [--size WxH]
Each round runs every variant (order alternates per round) through --bench-views and
records per-fixture min and median GPU frame times. Reports min-of-min, median-of-median
and the ratio to the first variant. Images from the last round are kept per variant.
"""
import argparse, csv, os, subprocess, statistics
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def parse_variant(text):
    name, rest = text.split('=', 1)
    parts = rest.split(';')
    exe = os.path.abspath(parts[0])
    env = dict(p.split('=', 1) for p in parts[1:] if p)
    return name, exe, env


def run(exe, out, size, frames, env_extra, fixtures):
    env = os.environ.copy()
    env.update(env_extra)
    w, h = size.split('x')
    err = os.path.join(os.path.dirname(exe), 'aurora-error.txt')
    if os.path.exists(err):
        os.remove(err)
    r = subprocess.run([exe, '--bench-views', out, w, h, str(frames)] + fixtures, cwd=os.path.dirname(exe), env=env)
    if r.returncode != 0:
        msg = open(err, encoding='utf-8', errors='replace').read() if os.path.exists(err) else ''
        raise SystemExit(f'{exe} failed ({r.returncode}): {msg}')
    return {row['fixture']: row for row in csv.DictReader(open(os.path.join(out, 'bench.csv')))}


def diff(a_path, b_path):
    a = np.asarray(Image.open(a_path).convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(b_path).convert('RGB'), dtype=np.int16)
    d = np.abs(a - b).max(axis=2)
    return d.mean(), int((d > 16).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', action='append', required=True)
    ap.add_argument('--rounds', type=int, default=3)
    ap.add_argument('--frames', type=int, default=16)
    ap.add_argument('--size', default='1980x1058')
    ap.add_argument('--fixtures', default='')
    ap.add_argument('--tag', default='ab')
    a = ap.parse_args()
    variants = [parse_variant(v) for v in a.variant]
    fx_dir = os.path.join(ROOT, 'fixtures')
    names = a.fixtures.split(',') if a.fixtures else sorted(f[:-7] for f in os.listdir(fx_dir) if f.endswith('.aurora'))
    fixtures = [os.path.join(fx_dir, n + '.aurora') for n in names]
    mins = {v[0]: {n: [] for n in names} for v in variants}
    meds = {v[0]: {n: [] for n in names} for v in variants}
    for r in range(a.rounds):
        order = variants if r % 2 == 0 else list(reversed(variants))
        for name, exe, env in order:
            out = os.path.join(ROOT, 'results', f'{a.tag}-{name}')
            rows = run(exe, out, a.size, a.frames, env, fixtures)
            for n in names:
                mins[name][n].append(float(rows[n]['min_ms']))
                meds[name][n].append(float(rows[n]['median_ms']))
    base = variants[0][0]
    header = f"{'fixture':24s}" + ''.join(f" {v[0][:14]:>14s}" for v in variants)
    print('min-of-min ms (ratio to first)')
    print(header)
    totals = {v[0]: 0.0 for v in variants}
    for n in names:
        line = f'{n:24s}'
        for v in variants:
            m = min(mins[v[0]][n])
            totals[v[0]] += m
            line += f' {m:7.2f}({m / min(mins[base][n]):5.3f})'
        print(line)
    print(f"{'TOTAL':24s}" + ''.join(f" {totals[v[0]]:7.2f}({totals[v[0]] / totals[base]:5.3f})" for v in variants))
    print('median-of-median ms')
    for n in names:
        line = f'{n:24s}'
        for v in variants:
            m = statistics.median(meds[v[0]][n])
            line += f' {m:7.2f}({m / statistics.median(meds[base][n]):5.3f})'
        print(line)
    print('image difference vs first variant (mean max-channel, pixels>16)')
    for v in variants[1:]:
        line = f'{v[0]:24s}'
        tot16 = 0
        worst = []
        for n in names:
            md, p16 = diff(os.path.join(ROOT, 'results', f'{a.tag}-{base}', n + '.png'),
                           os.path.join(ROOT, 'results', f'{a.tag}-{v[0]}', n + '.png'))
            tot16 += p16
            worst.append((p16, n, md))
        worst.sort(reverse=True)
        print(line, 'total px>16:', tot16, 'worst:', [(n, p, round(m, 3)) for p, n, m in worst[:4]])


if __name__ == '__main__':
    main()
