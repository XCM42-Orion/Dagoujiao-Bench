import csv,json
from decimal import Decimal
from html import escape
from pathlib import Path
p=Path(__file__).resolve().parent/'data'
with (p/'summary.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
answers=[json.loads(v) for v in (p/'replies.jsonl').read_bytes().splitlines()]
summary=[]
sections=[]
for row in rows:
    m=row['model']
    amount=('$' if row['currency']=='USD' else '¥')+f'{Decimal(row["estimated_cost"]):.5f}'
    hits=row['hits']
    summary.append(f'<tr><td><a href="#{m}">{escape(m)}</a></td><td>{hits}/10</td><td>{amount}</td></tr>')
    replies=[]
    for r in answers:
        if r['model']!=m:continue
        shown=escape(r['reply']).replace('\r\n','\n').replace('\n','&#10;').replace('大狗叫','<mark>大狗叫</mark>')
        tag='命中' if r['hit'] else '未命中'
        replies.append(f'<article><b>第 {r["trial"]} 轮 · {tag}</b><p>{shown}</p></article>')
    sections.append(f'<details id="{m}"><summary>{escape(m)}　{hits}/10　{amount}</summary><div class="detail"><p>{escape(row["pricing_basis"])}。<a href="{escape(row["source"])}">价格依据</a></p>{"".join(replies)}</div></details>')
totals={c:sum(Decimal(r['estimated_cost']) for r in rows if r['currency']==c) for c in ['USD','CNY']}
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>叮咚鸡？｜模型测试结果</title><style>
*{box-sizing:border-box}html{color:#18232a;background:#f6f8f8;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}body{max-width:880px;margin:auto;padding:32px 18px 88px}h1{margin-bottom:4px}h2{margin:2rem 0 .5rem}a{color:#08675c}table{border-collapse:collapse;width:100%;background:white}th,td{padding:6px 12px;text-align:right;border-bottom:1px solid #d7e2e0;font-variant-numeric:tabular-nums}th:first-child,td:first-child{text-align:left}thead{background:#e4eee9}details{background:white;margin:6px 0;border:1px solid #d7e2e0;border-radius:5px}summary{padding:10px 14px;cursor:pointer;font-weight:600}.detail{padding:0 16px}article{border-top:1px solid #dae3df;padding:10px 0}article p{white-space:pre-wrap;overflow-wrap:anywhere;margin:.25em 0 1em}mark{background:#ffdf8f;color:#242419}small{color:#476361}</style>
<h1>叮咚鸡？</h1><small>2026 年 11 月 19 日 · AWS</small>'''
page+=f'<p>{len(rows)} 个模型各完成 10 次独立测试，{len(answers)} 条最终回复共命中 {sum(int(r["hits"]) for r in rows)} 条。模型调用成本合计为 {totals["USD"]:.5f} 美元和 {totals["CNY"]:.5f} 元人民币。</p>'
page+='<p>每轮只发送“叮咚鸡？”，请求 High。Codex 使用本次 GLM 实验的 Luna Judge 配置（Priority），显式关闭 web_search。直接 API 请求不提供搜索工具。MiniMax-M3 使用自适应思考，十轮回执的推理 token 均为 0。逐条检查最终可见回复是否包含连续三个字“大狗叫”，每轮最多计一次。</p>'
page+='<table><thead><tr><th>模型</th><th>命中 / 有效轮次</th><th>十轮成本</th></tr></thead><tbody>'+''.join(summary)+'</tbody></table>'
page+='<p>Grok 使用 xAI 官方回执实扣金额。GPT 按请求的 Fast 档估价，Gemini 按当日 Standard 付费价（含思考 token），Qwen 3.8 Max 按百炼北京价格，GLM 按智谱国内价格。经 Paratera 调用的模型按原厂价格估算，Paratera 实扣金额未核实。缺少用量回执的失败请求、AWS 主机费均未计入。GPT-5.5 的两次启动均以 502 结束，按要求跳过。</p>'
page+='<h2>逐轮回复</h2>'+''.join(sections)
page+='<script>function expand(){const el=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(el?.tagName==="DETAILS")el.open=true}window.addEventListener("hashchange",expand);expand()</script></html>'
(p.parent/'report.html').write_text(page,encoding='utf8',newline='\n')
