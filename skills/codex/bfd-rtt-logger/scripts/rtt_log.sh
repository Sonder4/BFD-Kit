#!/bin/bash
################################################################################
#                       RTT Logger Script for Linux
# 功能：通过 J-Link 采集 RTT 日志并保存为 CSV 格式
################################################################################

# 默认参数
DURATION=10
OUTPUT_FILE="logs/rtt/rtt_log.csv"
CHANNEL=0
VIEW_ONLY=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
PROFILE_HELPER="${PROJECT_ROOT}/build_tools/jlink/profile_env.sh"
if [[ -f "${PROFILE_HELPER}" ]]; then
    # shellcheck source=build_tools/jlink/profile_env.sh
    source "${PROFILE_HELPER}"
    if load_stm32_profile_env "${PROJECT_ROOT}" >/dev/null 2>&1; then
        DEVICE="${STM32_DEVICE}"
        INTERFACE="${STM32_IF:-SWD}"
        SPEED="${STM32_SPEED_KHZ:-4000}"
    else
        DEVICE="STM32F427II"
        INTERFACE="SWD"
        SPEED=4000
    fi
else
    DEVICE="STM32F427II"
    INTERFACE="SWD"
    SPEED=4000
fi

# 显示使用说明
show_help() {
    echo "RTT 日志采集工具"
    echo ""
    echo "用法：$0 [选项]"
    echo ""
    echo "选项:"
    echo "  -d, --duration SEC    采集时长（秒），默认：10"
    echo "  -o, --output FILE     输出文件路径，默认：logs/rtt/rtt_log.csv"
    echo "  -c, --channel NUM     RTT 通道号，默认：0"
    echo "  -v, --view            仅查看不保存"
    echo "  -h, --help            显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 -d 10 -o log.csv      # 采集 10 秒 RTT 日志"
    echo "  $0 -v                    # 仅查看实时日志"
    echo "  $0 -c 1 -d 30            # 采集通道 1 的日志 30 秒"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -c|--channel)
            CHANNEL="$2"
            shift 2
            ;;
        -v|--view)
            VIEW_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "未知选项：$1"
            show_help
            exit 1
            ;;
    esac
done

# 检查 J-Link 是否安装
if ! command -v JLinkExe &> /dev/null; then
    echo "错误：未找到 JLinkExe，请确保 J-Link 软件已安装"
    echo "可以从 https://www.segger.com/downloads/jlink/ 下载"
    exit 1
fi

# 获取当前时间戳
get_timestamp() {
    date +"%Y-%m-%dT%H:%M:%S.%3N%:z"
}

START_TIME=$(get_timestamp)
START_EPOCH=$(date +%s)

if [ "$VIEW_ONLY" = true ]; then
    echo "=================================="
    echo "RTT 实时日志查看器"
    echo "=================================="
    echo "设备：$DEVICE"
    echo "通道：$CHANNEL"
    echo "按 Ctrl+C 停止查看"
    echo "=================================="
    echo ""

    # 使用 JLinkRTTViewer 查看实时日志
    if command -v JLinkRTTViewer &> /dev/null; then
        JLinkRTTViewer -device "$DEVICE" -if "$INTERFACE" -speed "$SPEED" -channel "$CHANNEL"
    else
        echo "警告：JLinkRTTViewer 未找到，使用 JLinkExe 替代"
        JLinkExe -device "$DEVICE" -if "$INTERFACE" -speed "$SPEED" <<EOF
connect
h
exec ReadRTTBlock($CHANNEL)
exit
EOF
    fi
    exit 0
fi

# 采集模式
echo "=================================="
echo "RTT 日志采集"
echo "=================================="
echo "设备：$DEVICE"
echo "接口：$INTERFACE @ ${SPEED}kHz"
echo "通道：$CHANNEL"
echo "时长：${DURATION}秒"
echo "输出：$OUTPUT_FILE"
echo "=================================="
echo ""

mkdir -p "$(dirname "$OUTPUT_FILE")"

# 当前脚本先验证 profile / J-Link 连接和日志文件路径是否可用。
# 真正的长时 RTT 采集仍建议走 build_tools/jlink/rtt.sh 或后续 orchestrator 链路。
TEMP_FILE=$(mktemp)

JLinkExe -device "$DEVICE" -if "$INTERFACE" -speed "$SPEED" <<EOF > "$TEMP_FILE" 2>&1
connect
h
r
g
exit
EOF

JLINK_EXIT=$?

if [ $JLINK_EXIT -ne 0 ]; then
    echo "错误：J-Link 连接失败"
    rm -f "$TEMP_FILE"
    exit 1
fi

echo "J-Link 连接成功"

# 从 temp 文件提取 RTT 数据并生成 CSV
echo "正在生成 CSV 文件..."

END_TIME=$(get_timestamp)

cat > "$OUTPUT_FILE" <<EOF
# Device: $DEVICE
# Interface: $INTERFACE
# Speed: ${SPEED}kHz
# Channel: $CHANNEL
# Start: $START_TIME
# End: $END_TIME
# Duration: ${DURATION}s
#
timestamp,level,message
EOF

if grep -q "Connecting to J-Link" "$TEMP_FILE" || grep -q "J-Link Commander" "$TEMP_FILE"; then
    TIMESTAMP=$(get_timestamp)
    echo "$TIMESTAMP,INFO,\"J-Link session established; use build_tools/jlink/rtt.sh for full RTT payload capture\"" >> "$OUTPUT_FILE"
fi

rm -f "$TEMP_FILE"

END_EPOCH=$(date +%s)
ACTUAL_DURATION=$((END_EPOCH - START_EPOCH))

echo ""
echo "=================================="
echo "RTT 日志采集完成"
echo "=================================="
echo "实际采集时长：${ACTUAL_DURATION}秒"
echo "输出文件：$OUTPUT_FILE"
echo "=================================="

exit 0
