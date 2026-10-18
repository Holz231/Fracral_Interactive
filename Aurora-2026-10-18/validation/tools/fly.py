"""Fly from saved views with fixed 1/60 s steps and summarise GPU frame times.

usage: python fly.py <exe> <tag> [--frames 300] [--speed 3.8] [--size 1980x1058] [--env K=V ...] [--fixtures a,b]
"""
import argparse, csv, os, statistics, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('exe')
    ap.add_argument('tag')
    ap.add_argument('--frames', type=int, default=300)
    ap.add_argument('--speed', type=float, default=3.8)
    ap.add_argument('--size', default='1980x1058')
    ap.add_argument('--every', type=int, default=0)
    ap.add_argument('--env', action='append', default=[])
    ap.add_argument('--fixtures', default='corner,heavy69,user-root-slow,user-preview0817-slow,user-root-last,interior')
    a = ap.parse_args()
    env = os.environ.copy()
    env.update(dict(e.split('=', 1) for e in a.env))
    exe = os.path.abspath(a.exe)
    w, h = a.size.split('x')
    allms = []
    print(f"{'fixture':24s} {'median':>7s} {'p95':>7s} {'max':>7s} {'>16.0':>6s} {'>14.5':>6s} {'zoom0':>6s} {'zoom1':>6s}")
    for n in a.fixtures.split(','):
        out = os.path.join(ROOT, 'results', f'{a.tag}-{n}')
        fx = os.path.join(ROOT, 'fixtures', n + '.aurora')
        err = os.path.join(os.path.dirname(exe), 'aurora-error.txt')
        if os.path.exists(err):
            os.remove(err)
        r = subprocess.run([exe, '--fly-views', out, w, h, str(a.frames), str(a.speed), str(a.every), fx], cwd=os.path.dirname(exe), env=env)
        if r.returncode:
            print(n, 'failed', open(err).read() if os.path.exists(err) else '')
            continue
        rows = list(csv.DictReader(open(os.path.join(out, 'flight.csv'))))
        ms = [float(x['gpu_ms']) for x in rows]
        allms += ms
        s = sorted(ms)
        print(f"{n:24s} {statistics.median(ms):7.2f} {s[int(len(s) * .95)]:7.2f} {max(ms):7.2f} {sum(m > 16 for m in ms):6d} {sum(m > 14.5 for m in ms):6d} {float(rows[0]['zoom']):6.1f} {float(rows[-1]['zoom']):6.1f}")
    s = sorted(allms)
    print(f"{'ALL':24s} {statistics.median(allms):7.2f} {s[int(len(s) * .95)]:7.2f} {max(allms):7.2f} {sum(m > 16 for m in allms):6d} {sum(m > 14.5 for m in allms):6d}")


if __name__ == '__main__':
    main()
