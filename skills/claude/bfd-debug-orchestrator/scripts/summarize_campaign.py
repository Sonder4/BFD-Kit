#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

SOFTFAULT_STRONG_SIGNALS = {"scenario_log", "fallback_scenario_log", "live_scenario_log"}
ADVISORY_RTT_TAGS = {"rtt_base"}
REQUIRED_BOOT_TAGS = {"rtt_final"}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def parse_key_value_lines(path: Path):
    values = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return values

    for match in re.finditer(r"(RTT_[A-Z0-9_]+)=([^\r\n]+)", text):
        values[match.group(1)] = match.group(2).strip()
    return values


def infer_capture_role(tag: str, meta):
    explicit_role = meta.get("RTT_ROLE")
    if explicit_role:
        return explicit_role
    if re.fullmatch(r"rtt_s[12]", tag):
        return "diag"
    return "boot"


def infer_requirement_role(tag: str):
    if tag in ADVISORY_RTT_TAGS:
        return "advisory"
    return "required"


def classify_rtt_log(path: Path):
    meta = parse_key_value_lines(path)
    tag = path.stem
    success = meta.get("RTT_SUCCESS", "0") == "1"
    signal = meta.get("RTT_SIGNAL", "missing_result")
    mode = meta.get("RTT_MODE", "unknown")
    command_rc = meta.get("RTT_COMMAND_RC", "unknown")
    capture_role = infer_capture_role(tag, meta)
    role = infer_requirement_role(tag)
    channel = meta.get("RTT_CHANNEL", "unknown")
    status = "PASS" if success else "WARN"
    detail = signal

    if re.fullmatch(r"rtt_s[12]", tag):
        role = "required"
        capture_role = "diag"
        if success and signal in SOFTFAULT_STRONG_SIGNALS:
            status = "PASS"
            detail = signal
        else:
            status = "WARN"
            detail = f"need scenario evidence, got {signal}"
    elif re.fullmatch(r"rtt_recover_s[0-9]+", tag) or tag in REQUIRED_BOOT_TAGS:
        role = "required"
        capture_role = "boot"
        status = "PASS" if success else "WARN"
        detail = signal if success else f"boot evidence missing ({signal})"
    elif tag in ADVISORY_RTT_TAGS:
        role = "advisory"
        status = "PASS" if success else "WARN"
        detail = signal if success else f"advisory capture weak ({signal})"

    return {
        "tag": tag,
        "path": str(path),
        "mode": mode,
        "role": role,
        "capture_role": capture_role,
        "channel": channel,
        "status": status,
        "signal": signal,
        "detail": detail,
        "success": success,
        "command_rc": command_rc,
    }


def collect_rtt_results(session_dir: Path):
    return [classify_rtt_log(path) for path in sorted(session_dir.glob("rtt_*.log"))]


def aggregate_rtt_status(results):
    required = [item for item in results if item["role"] == "required"]
    advisory = [item for item in results if item["role"] == "advisory"]

    required_status = "PASS"
    advisory_status = "PASS"

    if any(item["status"] != "PASS" for item in required):
        required_status = "WARN"
    if any(item["status"] != "PASS" for item in advisory):
        advisory_status = "WARN"

    return {
        "overall": required_status,
        "required": required_status,
        "advisory": advisory_status,
        "required_failures": [item["tag"] for item in required if item["status"] != "PASS"],
        "advisory_failures": [item["tag"] for item in advisory if item["status"] != "PASS"],
    }


def main():
    parser = argparse.ArgumentParser(description="汇总调试活动结果")
    parser.add_argument("--session-dir", required=True, help="会话目录")
    parser.add_argument(
        "--output",
        default=".codex/debug/bfd-debug-orchestrator-campaign.md",
        help="汇总输出 Markdown",
    )
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    hardfault_jsons = sorted(session_dir.glob("hardfault_*.json"))
    step_logs = sorted(session_dir.glob("*.log"))
    rtt_results = collect_rtt_results(session_dir)
    rtt_status = aggregate_rtt_status(rtt_results)

    faults = []
    for path in hardfault_jsons:
        data = read_json(path)
        if not data:
            continue
        faults.append(
            {
                "id": data.get("id", path.stem),
                "type": data.get("fault_type", "Unknown"),
                "pc": data.get("registers", {}).get("PC", "N/A"),
                "cfsr": data.get("fault_status", {}).get("CFSR", "N/A"),
                "path": str(path),
            }
        )

    lines = [
        "# BFD Debug Orchestrator Campaign",
        "",
        "## 结论",
        f"- 会话目录: {session_dir}",
        f"- 生成时间: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- HardFault 记录数: {len(faults)}",
        f"- RTT 总状态: {rtt_status['overall']}",
        f"- RTT 必选状态: {rtt_status['required']}",
        f"- RTT 附加状态: {rtt_status['advisory']}",
        "",
        "## RTT 摘要",
    ]

    if rtt_results:
        for item in rtt_results:
            lines.append(
                f"- {item['tag']} | capture={item['capture_role']} | role={item['role']} | channel={item['channel']} | status={item['status']} | mode={item['mode']} | signal={item['signal']} | {item['path']}"
            )
    else:
        lines.append("- 未发现 RTT 会话日志")

    if rtt_status["required_failures"]:
        lines.append(f"- RTT 必选失败: {', '.join(rtt_status['required_failures'])}")
    if rtt_status["advisory_failures"]:
        lines.append(f"- RTT 附加告警: {', '.join(rtt_status['advisory_failures'])}")

    lines += ["", "## 关键证据路径"]
    for path in step_logs[:20]:
        lines.append(f"- {path}")

    if faults:
        lines += ["", "## HardFault 关键摘要"]
        for fault in faults:
            lines.append(
                f"- {fault['id']} | {fault['type']} | PC={fault['pc']} | CFSR={fault['cfsr']} | {fault['path']}"
            )

    lines += [
        "",
        "## 下一步",
        "- 对重复 signature 优先复用 error-evolution 中已有修复手册。",
        "- 若 boot dual 仍偶发空载荷，优先检查 channel 0 attach/reset 时序与原始 raw 日志。",
    ]

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SUMMARY_OUT={out_path}")
    print(f"RTT_CAPTURE_STATUS={rtt_status['overall']}")
    print(f"RTT_REQUIRED_STATUS={rtt_status['required']}")
    print(f"RTT_ADVISORY_STATUS={rtt_status['advisory']}")


if __name__ == "__main__":
    main()
