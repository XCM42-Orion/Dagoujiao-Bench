"""Verify the benchmark matrix and produce audit-ready results from AWS records."""
import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path
import json

P = Path(__file__).resolve().parent / 'data'
OPENAI = 'https://developers.openai.com/api/docs/pricing.md'
GOOGLE = 'https://aistudio.google.com/docs/pricing'
DS = 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
# USD or CNY per million tokens in the order input, read, write, output.
rates = {
    'grok-4.7': (None,)*4,
    'grok-4.6': (None,)*4,
    'GLM-5.3': (8,2,0,28),
    'MiniMax-M3': (2.10,.42,0,8.40),
    'Kimi-K3': (20,2,20,100),
    'gpt-5.6-luna': (.4,.04,.5,2.4),
    'gpt-5.6-terra': (4,.4,5,24),
    'gpt-5.6-sol': (8,.8,10,40),
    'gpt-6-astra': (20,2,25,100),
    'gpt-6.1-sol': (4,.2,5,20),
    'gpt-6.2-astra': (16,.8,20,80),
    'gpt-6.2-sol': (4,.2,5,20),
    'qwen3.8-max': (12,1.5,15,36),
    'glm-5.3-flash': (.8,.23,0,2.8),
    'DeepSeek-V4.1-Flash-1017': (2,.04,0,8),
    'Hy4': (6,.3,0,18),
    'Qwen4-Max': (10,.5,0,30),
    'Kimi-K3.1-Pro': (13,1.3,13,68),
    'DeepSeek-V4-Pro-0813': (9,.3,0,27),
    'gemini-3.8-flash': (.75,.075,0,3.75),
    'gemini-4-hydrogen': (1.5,.075,0,7.5),
    'gemini-4-neon': (3,.15,0,15),
    'gemini-4-argon': (2,.1,0,10),
    'gemini-4-carbon': (2,.1,0,10),
}
para_sources = {
    'GLM-5.3':'https://docs.bigmodel.cn/cn/guide/start/pricing',
    'MiniMax-M3':'https://platform.minimax.cn/docs/pricing/overview',
    'Kimi-K3':'https://www.kimi.com/resources/model-api',
    'DeepSeek-V4.1-Flash-1017':DS, 'DeepSeek-V4-Pro-0813':DS,
    'Hy4':'https://cloud.tencent.com/document/product/1823/130055/',
    'Qwen4-Max':'https://help.aliyun.com/en/model-studio/qwen4-max',
    'Kimi-K3.1-Pro':'https://www.kimi.com/resources/kimi-k3-1-pro-pricing',
}

def usage(m,u):
    if m.startswith('gpt-'):
        i,c,w,o = (u[k] for k in ['input_tokens','cached_input_tokens','cache_write_input_tokens','output_tokens'])
        return i-c-w,c,w,o
    if m.startswith('gemini-'):
        i=u['promptTokenCount']
        c=u.get('cachedContentTokenCount',0)
        o=u['candidatesTokenCount']+u.get('thoughtsTokenCount',0)
        assert u['totalTokenCount']==i+o and u['serviceTier']=='standard',u
        return i-c,c,0,o
    if m=='qwen3.8-max':
        return u['input_tokens'],u.get('cache_read_input_tokens',0),u.get('cache_creation_input_tokens',0),u['output_tokens']
    i=u['prompt_tokens']
    c=u.get('prompt_tokens_details',{}).get('cached_tokens',u.get('cache_read_input_tokens',0))
    if m.startswith('grok-'):
        o=u['completion_tokens']+u['completion_tokens_details']['reasoning_tokens']
        assert i+o==u['total_tokens'] and u['num_sources_used']==0
        return i-c,c,0,o
    w=u.get('cache_creation_input_tokens',0)
    assert not w or rates[m][2]
    return i-c-w,c,w,u['completion_tokens']

def pricing(m):
    if m.startswith('grok-'):return 'USD','xAI 官方 API 逐轮回执实扣','https://docs.x.ai/developers/cost-tracking'
    if m in para_sources:return 'CNY','原厂人民币目录参考价（DeepSeek 取北京时间高峰价，Hy4 取刊例原价）；Paratera 账户实扣未核实',para_sources[m]
    if m.startswith('gpt-'):return 'USD','按请求的 Priority/Fast 短上下文公开价估算；中转站实扣未核实',OPENAI
    if m.startswith('gemini-'):return 'USD','Google Standard 付费档，含思考 token，按 2026-11-19 有效价格',GOOGLE
    if m=='qwen3.8-max':return 'CNY','百炼北京地域公开价','https://help.aliyun.com/zh/model-studio/qwen3-8-max'
    return 'CNY','智谱开放平台国内公开价','https://docs.bigmodel.cn/cn/guide/start/pricing'

valid=[json.loads(line) for line in (P/'replies.jsonl').read_bytes().splitlines()]
assert Counter(r['model'] for r in valid)=={m:10 for m in rates}
summary=[]
for m,rate in rates.items():
    rows=sorted([r for r in valid if r['model']==m],key=lambda r:r['trial'])
    assert [r['trial'] for r in rows]==list(range(1,11))
    cur,basis,source=pricing(m)
    total=Decimal(0)
    counts=[0]*4
    for r in rows:
        assert r['hit']==('大狗叫' in r['reply'])
        use=usage(m,r['usage'])
        assert min(use)>=0
        if m.startswith('grok-'):
            price=Decimal(r['usage']['cost_in_usd_ticks'])/10_000_000_000
        else:
            price=sum(Decimal(str(a))*b for a,b in zip(rate,use))/1000000
        total+=price
        counts=[a+b for a,b in zip(counts,use)]
        assert price==Decimal(r['estimated_cost']) and cur==r['currency']
    historical={'qwen3.8-max':(2,.25,2.5,6),'glm-5.3-flash':(.15,.03,0,.5)}.get(m)
    comparison=str(sum(Decimal(str(a))*b for a,b in zip(historical,counts))/1000000) if historical else ''
    summary.append(dict(model=m,valid=len(rows),hits=sum(x['hit'] for x in rows),currency=cur,estimated_cost=str(total),pptbench_reference_usd=comparison,
                        uncached_input=counts[0],cache_read=counts[1],cache_write=counts[2],output_including_reasoning=counts[3],
                        rate_input=rate[0],rate_cache_read=rate[1],rate_cache_write=rate[2],rate_output=rate[3],pricing_basis=basis,source=source))
with (P/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=summary[0].keys(),lineterminator='\n');writer.writeheader();writer.writerows(summary)
for row in summary:print(row['model'],row['hits'],row['currency'],row['estimated_cost'])
print('totals',sum(r['hits'] for r in summary),{c:str(sum(Decimal(r['estimated_cost']) for r in summary if r['currency']==c)) for c in ['USD','CNY']})
