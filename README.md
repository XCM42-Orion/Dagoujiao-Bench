# 大狗叫 Bench

[By ShiritaiBot Devs](https://shiritaibot.dev)

给模型发「叮咚鸡？」。每个模型独立回答十次，最终可见回复包含连续的「大狗叫」就算命中。Index 等于命中次数乘以 10。2026 年 11 月 19 日的 AWS 与本机实测覆盖 26 个模型，260 条有效回复共命中 124 次。

下载后直接打开 [index.html](index.html)，即可离线浏览排行榜、成本和 token 效率前沿、回复样例与逐轮对照。

## 数据与复算

- [逐轮回复](data/replies.jsonl) 保留完整可见答复、模型、轮次、命中结果、用量与费用。模型与轮次共同标识每条记录。
- [尝试记录](data/attempts.jsonl) 包含成功与失败的尝试序号、状态和可用的 HTTP 状态码。GPT-5.5 启动失败后跳过。
- [请求配置](data/protocols.json) 保留实际采用的 API 请求体或 Codex 命令参数。临时目录和结果文件名使用占位符。
- [汇总表](data/summary.csv) 包含分项 token、币种、计价依据和单价。xAI 使用回执实扣，其余按表中费率估算。图表将人民币成本按 1 美元兑 6.7118 元折算。token 前沿统计十轮总输入与输出，包含回执计入的缓存、思考和 Harness 上下文。

使用 Python 3.10 或更高版本，无需第三方依赖。在仓库根目录运行以下命令即可校验发布数据，复算汇总表并生成逐轮报告。

```sh
python -X utf8 summarize.py
python -X utf8 report.py
```

## 重新采样

各模型请求 High，直调 API 时不传搜索工具。MiniMax-M3 使用自适应思考。GPT 使用已登录的 Codex CLI 和 Luna Judge 实验的 Priority 配置，命令显式关闭 web_search。复现 GPT 需要兼容发布参数的 CLI 及有相应模型权限的提供商配置。可用 CODEX_BIN 指定可执行文件，CODEX_HOME 指向自己的配置。

按需在环境变量中提供所选服务的凭据。GEMINI_API_KEY、XAI_API_KEY、PARATERA_API_KEY 分别对应官方 Gemini、官方 xAI 和 Paratera。GLM 使用 GLM_API_KEY 和 GLM_BASE_URL（包含版本路径）；Qwen 3.8 Max 使用 QWEN_API_KEY 和 QWEN_BASE_URL（Anthropic 兼容端点根地址，脚本追加 /v1/messages）。

```sh
python run.py glm-5.3-flash
python run.py gpt-6.2-sol gemini-4-argon --workers 2
```

每款模型采样十次。结果写入 runs/，再次运行会跳过已成功的轮次。发布数据对应原实验；新的在线采样受模型版本、权限和提供商配置影响。

图标来自 @lobehub/icons-static-svg 1.104.0，MIT 许可声明已内嵌在 HTML 中。

Claude 补测使用本机 Antigravity CLI 1.5.12。可用 AGY_BIN 指定程序路径，再运行 `python run.py claude-opus-5-5-high claude-sonnet-5-5-high`。主代理仅允许 finish，逐轮确认没有工具调用。Claude 的 token 总量将 agy 单列的缓存读取加回 total_tokens；费用按 Anthropic 标准 API 输入、缓存读取及输出单价估算。agy 未返回账单或缓存写入明细。
