# Feature Requests

用户请求的能力、脚本增强点、skill 可读性或稳定性改进项。

**Statuses**: pending | resolved | promoted

---

- id: feature-20260311-bfd-kit-self-improvement-loop
  status: resolved
  summary: 为 BFD-Kit 建立问题解决后的 learning 记录与 skill/script 回写机制。

- id: feature-20260312-bfd-symbol-auto-focus-fields
  status: pending
  summary: 为 symbol-auto 增加“字段聚焦/字段优先级”输出能力，例如 `--focus measure.ecd,measure.speed_rpm,measure.real_current,measure.temperature`，避免 AI 在硬件验证时还需要在 skill 外用一次性 Python 对 JSON 做二次提取。

- id: feature-20260313-jlink-hss-multi-block-decode
  status: promoted
  summary: 为原生 J-Link HSS 路径补齐多 block 描述结构解析、multi-symbol 同步采样和更准确的 capability 字段语义，避免第一版仅限单个固定地址标量。
