"""Summarize Nsight's tab-separated .xls exports without an Excel dependency."""
import csv
import json
from pathlib import Path

validation=Path(__file__).resolve().parent
root=validation/'tools/nsight'
hardware=root/'capture-hardware/BASE_UNLOCKED'
shader=root/'capture-shader/BASE_UNLOCKED'

def rows(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig'),delimiter='\t'))

times={r['event_text']:float(r['time_ms']) for r in rows(hardware/'D3DPERF_EVENTS.xls')}
stalls={r['flattened_event_name']:r for r in rows(shader/'GPUTRACE_REGIMES.xls')}
metrics=[]
for r in rows(hardware/'GPUTRACE_REGIMES.xls'):
    name=r['flattened_event_name']
    item={'phase':name,'ms':times[name],
        'sm_throughput_pct':float(r['GPUTrace.sm__throughput.avg.pct_of_peak_sustained_elapsed']),
        'active_lanes_per_warp':float(r['smsp__thread_inst_executed_per_inst_executed.ratio']),
        'active_warps_per_sm':float(r['TPC.TriageSCG.tpc__warps_active_shader_cs_realtime.avg.per_cycle_elapsed']),
        'register_allocation_pct':float(r['TPC.TriageSCG.tpc__sm_rf_registers_allocated_shader_cs_realtime.avg.pct_of_peak_sustained_elapsed'])}
    stall=stalls[name]
    active=float(stall['tpc__warps_active_shader_cs_realtime.avg.per_cycle_elapsed'])
    for reason in ('wait','short_scoreboard','long_scoreboard_pipe_l1tex','not_selected','barrier'):
        item[reason+'_active_warp_pct']=100*float(stall['GPUTrace.PCSampler.tpc__warps_issue_stalled_'+reason+'.avg.per_cycle_elapsed'])/max(active,1e-30)
    metrics.append(item)

output=validation/'nsight-2026-10-16-phases.csv'
with output.open('w',newline='',encoding='utf-8') as file:
    writer=csv.DictWriter(file,fieldnames=metrics[0].keys())
    writer.writeheader();writer.writerows(metrics)
summary={'initial_ms':times['Initial64'],
    'trace_1_to_4_ms':sum(times['Trace'+str(i)] for i in range(1,5)),
    'trace_5_to_16_ms':sum(times['Trace'+str(i)] for i in range(5,17)),
    'trace_17_to_32_ms':sum(times['Trace'+str(i)] for i in range(17,33)),
    'queue_ms':sum(v for k,v in times.items() if k.startswith('Queue')),
    'refine_ms':times['Refine']}
summary['sum_ms']=sum(summary.values())
print(json.dumps(summary,indent=2))
