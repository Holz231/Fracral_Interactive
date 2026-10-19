"""Exact arithmetic fast paths motivated by the Nsight instruction/latency trace.

Generate isolated shaders; never alter the installed renderer or its oracle.
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
source = (root / 'src/fractal.hlsl').read_text(encoding='utf-8')
for name, fold, sphere in [('fold-branch', True, False),
                            ('sphere-branch', False, True),
                            ('field-branches', True, True)]:
    result = source
    if fold:
        old = '    return inner?delta:outer?-delta:2*clamp(p,-1,1)-p-folded;'
        new = '''    [branch] if(all(inner|outer)) return outer?-delta:delta;
    return inner?delta:outer?-delta:2*clamp(p,-1,1)-p-folded;'''
        assert result.count(old) == 1
        result = result.replace(old, new)
    if sphere:
        old = '        delta=k*(delta-s.q.xyz*(dc/s.q.w));p=s.next.xyz+delta;derivative*=k;'
        new = '''        [branch] if(dc==0) delta=k*delta;
        else delta=k*(delta-s.q.xyz*(dc/s.q.w));
        p=s.next.xyz+delta;derivative*=k;'''
        assert result.count(old) == 1
        result = result.replace(old, new)
    output = root / 'validation/experiments' / name
    output.mkdir(parents=True, exist_ok=True)
    (output / 'fractal.hlsl').write_text(result, encoding='utf-8')

old='        float k=2.8/clamp(dot(q,q),.25,1);'
assert source.count(old)==1
result=source.replace(old,'''        float squared=dot(q,q),k=2.8;
        [branch] if(squared<1) k=2.8/max(squared,.25);''')
output=root/'validation/experiments/direct-sphere-branch'
output.mkdir(parents=True,exist_ok=True)
(output/'fractal.hlsl').write_text(result,encoding='utf-8')
