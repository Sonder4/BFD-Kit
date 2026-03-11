#!/bin/bash
################################################################################
#                 寄存器数据采集脚本 for Linux (STM32F427 适配版)
# 功能：通过 J-Link 采集 STM32 外设寄存器并导出为 CSV 格式
################################################################################

# 默认参数
PERIPHERAL="USART1"
REGISTERS=""
DURATION=10
OUTPUT_FILE=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
PROFILE_HELPER="${PROJECT_ROOT}/build_tools/jlink/profile_env.sh"
if [[ -f "${PROFILE_HELPER}" ]]; then
    # shellcheck source=build_tools/jlink/profile_env.sh
    source "${PROFILE_HELPER}"
    if load_stm32_profile_env "${PROJECT_ROOT}" >/dev/null 2>&1; then
        DEVICE="${STM32_DEVICE}"
    else
        DEVICE="STM32F427II"
    fi
else
    DEVICE="STM32F427II"
fi
INTERFACE="SWD"
SPEED=4000
STATUS_ONLY=false
SAMPLE_INTERVAL=0

# STM32F427 外设地址表
# 仅保留本项目当前调试链路需要的常见外设，避免采样未知地址。
declare -A PERIPHERAL_ADDRESSES=(
    ["USART1"]="0x40011000"
    ["USART2"]="0x40004400"
    ["USART3"]="0x40004800"
    ["UART4"]="0x40004C00"
    ["UART5"]="0x40005000"
    ["USART6"]="0x40011400"
    ["SPI1"]="0x40013000"
    ["SPI2"]="0x40003800"
    ["SPI3"]="0x40003C00"
    ["I2C1"]="0x40005400"
    ["I2C2"]="0x40005800"
    ["I2C3"]="0x40005C00"
    ["CAN1"]="0x40006400"
    ["CAN2"]="0x40006800"
)

# USART 寄存器偏移量和名称
# F4 USART 使用 SR/DR/BRR/CRx 等寄存器布局。
declare -A USART_REGISTERS=(
    ["SR"]="0x00|Status Register"
    ["DR"]="0x04|Data Register"
    ["BRR"]="0x08|Baud Rate Register"
    ["CR1"]="0x0C|Control Register 1"
    ["CR2"]="0x10|Control Register 2"
    ["CR3"]="0x14|Control Register 3"
    ["GTPR"]="0x18|Guard Time and Prescaler Register"
)

# bxCAN 寄存器偏移量和名称
# CAN2 为从控制器，寄存器布局与 CAN1 保持一致。
declare -A BXCAN_REGISTERS=(
    ["MCR"]="0x00|Master Control Register"
    ["MSR"]="0x04|Master Status Register"
    ["TSR"]="0x08|Transmit Status Register"
    ["RF0R"]="0x0C|Receive FIFO 0 Register"
    ["RF1R"]="0x10|Receive FIFO 1 Register"
    ["IER"]="0x14|Interrupt Enable Register"
    ["ESR"]="0x18|Error Status Register"
    ["BTR"]="0x1C|Bit Timing Register"
)

show_help() {
    echo "STM32 寄存器数据采集工具"
    echo ""
    echo "用法：$0 [选项]"
    echo ""
    echo "选项:"
    echo "  -p, --peripheral NAME   外设名称，默认：USART1"
    echo "  -r, --registers LIST    寄存器列表（逗号分隔），默认：该外设常用寄存器"
    echo "  -d, --duration SEC      采集时长（秒），默认：10"
    echo "  -o, --output FILE       输出文件路径"
    echo "  -i, --interval MS       采样间隔（毫秒），默认：0(J-Link 最快速度)"
    echo "  -s, --status            快速查看 CAN 状态（仅 CAN1/CAN2）"
    echo "  -h, --help              显示帮助信息"
    echo ""
    echo "支持的外设:"
    for key in "${!PERIPHERAL_ADDRESSES[@]}"; do
        echo "  $key - 基地址：${PERIPHERAL_ADDRESSES[$key]}"
    done
    echo ""
    echo "示例:"
    echo "  $0 -p USART1 -d 1"
    echo "  $0 -p CAN1 -r MCR,MSR,TSR,RF0R,RF1R,ESR,BTR -d 5"
    echo "  $0 -p CAN1 -s"
    echo "  $0 -p USART1 -r SR,DR,BRR -d 10"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--peripheral)
            PERIPHERAL="$2"
            shift 2
            ;;
        -r|--registers)
            REGISTERS="$2"
            shift 2
            ;;
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -i|--interval)
            SAMPLE_INTERVAL="$2"
            shift 2
            ;;
        -s|--status)
            STATUS_ONLY=true
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

if [ -z "$PERIPHERAL" ]; then
    echo "错误：必须指定外设名称 (-p)"
    show_help
    exit 1
fi

if [ -z "${PERIPHERAL_ADDRESSES[$PERIPHERAL]}" ]; then
    echo "错误：不支持的外设 '$PERIPHERAL'"
    echo "支持的外设列表:"
    for key in "${!PERIPHERAL_ADDRESSES[@]}"; do
        echo "  $key"
    done
    exit 1
fi

BASE_ADDRESS="${PERIPHERAL_ADDRESSES[$PERIPHERAL]}"

if [ -z "$OUTPUT_FILE" ]; then
    OUTPUT_FILE="logs/debug/${PERIPHERAL,,}_capture_$(date +%Y%m%d_%H%M%S).csv"
fi
mkdir -p "$(dirname "$OUTPUT_FILE")"

if ! command -v JLinkExe &> /dev/null; then
    echo "错误：未找到 JLinkExe，请确保 J-Link 软件已安装"
    exit 1
fi

get_timestamp() {
    date +"%Y-%m-%dT%H:%M:%S.%3N%:z"
}

get_register_info() {
    local peripheral="$1"
    local reg="$2"

    if [[ "$peripheral" == CAN* ]]; then
        printf '%s' "${BXCAN_REGISTERS[$reg]}"
        return
    fi

    if [[ "$peripheral" == USART* ]] || [[ "$peripheral" == UART* ]]; then
        printf '%s' "${USART_REGISTERS[$reg]}"
        return
    fi

    printf '%s' ''
}

decode_bxcan_status() {
    local mcr=$1
    local msr=$2
    local tsr=$3
    local rf0r=$4
    local rf1r=$5
    local esr=$6
    local btr=$7

    local inrq=$((mcr & 0x1))
    local sleep=$(((mcr >> 1) & 0x1))
    local txm=$(((btr >> 30) & 0x1))
    local lbkm=$(((btr >> 31) & 0x1))
    local erri=$(((msr >> 2) & 0x1))
    local slaki=$(((msr >> 1) & 0x1))
    local inak=$((msr & 0x1))
    local f0fl=$((rf0r & 0x3))
    local f1fl=$((rf1r & 0x3))
    local rec=$((esr & 0xFF))
    local tec=$(((esr >> 16) & 0xFF))
    local lec=$(((esr >> 4) & 0x7))

    echo ""
    echo "========== bxCAN 状态分析 =========="
    echo "[MCR 主控制寄存器]"
    if [ "$inrq" -eq 1 ]; then
        echo "  - INRQ=1: 控制器仍处于初始化请求状态"
    else
        echo "  - INRQ=0: 控制器处于正常工作请求状态"
    fi
    echo "  - SLEEP=$sleep"

    echo ""
    echo "[MSR 主状态寄存器]"
    echo "  - INAK=$inak"
    echo "  - SLAKI=$slaki"
    echo "  - ERRI=$erri"

    echo ""
    echo "[ESR 错误状态寄存器]"
    echo "  - REC (接收错误计数): $rec"
    echo "  - TEC (发送错误计数): $tec"
    case $lec in
        0) echo "  - LEC=0: 无错误" ;;
        1) echo "  - LEC=1: Stuff 错误" ;;
        2) echo "  - LEC=2: Form 错误" ;;
        3) echo "  - LEC=3: ACK 错误" ;;
        4) echo "  - LEC=4: Bit recessive 错误" ;;
        5) echo "  - LEC=5: Bit dominant 错误" ;;
        6) echo "  - LEC=6: CRC 错误" ;;
        7) echo "  - LEC=7: 软件置位/最近无变化" ;;
    esac

    echo ""
    echo "[FIFO 状态]"
    echo "  - RF0R FIFO0 消息数: $f0fl"
    echo "  - RF1R FIFO1 消息数: $f1fl"

    echo ""
    echo "[BTR 位时序寄存器]"
    echo "  - TXM=$txm"
    echo "  - LBKM=$lbkm"

    echo ""
    echo "[TSR 发送状态寄存器]"
    printf '  - TSR = 0x%08X\n' "$tsr"
    echo "===================================="
}

bxcan_quick_status() {
    local quick_regs=("MCR" "MSR" "TSR" "RF0R" "RF1R" "ESR" "BTR")
    declare -A reg_values

    echo "=================================="
    echo "bxCAN 快速状态查看"
    echo "=================================="
    echo "设备：$DEVICE"
    echo "外设：$PERIPHERAL (基地址：$BASE_ADDRESS)"
    echo "=================================="

    for reg in "${quick_regs[@]}"; do
        local reg_info
        reg_info="$(get_register_info "$PERIPHERAL" "$reg")"
        local offset
        offset=$(echo "$reg_info" | cut -d'|' -f1)
        local address=$((BASE_ADDRESS + offset))

        local value
        value=$(JLinkExe -device "$DEVICE" -if "$INTERFACE" -speed "$SPEED" <<EOF 2>/dev/null
connect
h
mem32 $(printf "0x%08X" "$address"),1
exit
EOF
)
        local hex_value
        hex_value=$(printf '%s\n' "$value" | grep -oE '0x[0-9A-Fa-f]+' | tail -1)
        if [ -z "$hex_value" ]; then
            hex_value="0x00000000"
        fi
        reg_values[$reg]=$hex_value
    done

    echo ""
    echo "寄存器原始值:"
    for reg in "${quick_regs[@]}"; do
        echo "  $reg = ${reg_values[$reg]}"
    done

    decode_bxcan_status \
        $((16#${reg_values[MCR]#0x})) \
        $((16#${reg_values[MSR]#0x})) \
        $((16#${reg_values[TSR]#0x})) \
        $((16#${reg_values[RF0R]#0x})) \
        $((16#${reg_values[RF1R]#0x})) \
        $((16#${reg_values[ESR]#0x})) \
        $((16#${reg_values[BTR]#0x}))
}

echo "=================================="
echo "寄存器数据采集"
echo "=================================="
echo "设备：$DEVICE"
echo "外设：$PERIPHERAL (基地址：$BASE_ADDRESS)"
echo "时长：${DURATION}秒"
echo "输出：$OUTPUT_FILE"
echo "=================================="
echo ""

if [ -n "$REGISTERS" ]; then
    IFS=',' read -ra REG_ARRAY <<< "$REGISTERS"
else
    case $PERIPHERAL in
        USART*|UART*)
            REG_ARRAY=("SR" "DR" "BRR" "CR1" "CR2" "CR3")
            ;;
        CAN*)
            REG_ARRAY=("MCR" "MSR" "TSR" "RF0R" "RF1R" "ESR" "BTR")
            ;;
        *)
            echo "错误：当前外设未配置默认寄存器列表，请使用 -r 指定寄存器"
            exit 1
            ;;
    esac
fi

if [ "$STATUS_ONLY" = true ]; then
    if [[ "$PERIPHERAL" != CAN* ]]; then
        echo "错误：--status 参数仅支持 CAN1/CAN2"
        exit 1
    fi
    echo "快速查看 bxCAN 状态..."
    bxcan_quick_status
    exit 0
fi

echo "采集寄存器：${REG_ARRAY[*]}"
if [ "$SAMPLE_INTERVAL" -eq 0 ]; then
    echo "采样间隔：无 (J-Link 最快速度采集)"
else
    echo "采样间隔：${SAMPLE_INTERVAL}ms"
fi
echo ""

START_TIME=$(get_timestamp)
HEADER="timestamp"
for reg in "${REG_ARRAY[@]}"; do
    HEADER="$HEADER,$reg"
done

cat > "$OUTPUT_FILE" <<EOF
# Device: $DEVICE
# Peripheral: $PERIPHERAL
# Base Address: $BASE_ADDRESS
# Capture Start: $START_TIME
# Duration: ${DURATION}s
# Interval: ${SAMPLE_INTERVAL}ms
#
$HEADER
EOF

echo "开始采集..."
echo "按 Ctrl+C 可随时停止"
echo ""

START_EPOCH=$(date +%s.%N)
SAMPLE_COUNT=0

while true; do
    CURRENT_EPOCH=$(date +%s.%N)
    ELAPSED=$(echo "$CURRENT_EPOCH - $START_EPOCH" | bc)
    if (( $(echo "$ELAPSED >= $DURATION" | bc -l) )); then
        break
    fi

    TIMESTAMP=$(get_timestamp)
    ROW="$TIMESTAMP"
    JLINK_CMDS="connect\nh\n"

    for reg in "${REG_ARRAY[@]}"; do
        reg_info="$(get_register_info "$PERIPHERAL" "$reg")"
        if [ -z "$reg_info" ]; then
            echo "错误：外设 $PERIPHERAL 不支持寄存器 $reg"
            exit 1
        fi
        offset=$(echo "$reg_info" | cut -d'|' -f1)
        address=$((BASE_ADDRESS + offset))
        JLINK_CMDS+="mem32 $(printf \"0x%08X\" \"$address\"),1\n"
    done
    JLINK_CMDS+="exit\n"

    value=$(JLinkExe -device "$DEVICE" -if "$INTERFACE" -speed "$SPEED" <<EOF 2>/dev/null
$JLINK_CMDS
EOF
)

    mapfile -t hex_values < <(printf '%s\n' "$value" | grep -oE '0x[0-9A-Fa-f]+' )
    if [ "${#hex_values[@]}" -gt 0 ]; then
        hex_values=("${hex_values[@]:1}")
    fi

    for idx in "${!REG_ARRAY[@]}"; do
        hex_value="${hex_values[$idx]:-0x00000000}"
        ROW="$ROW,$hex_value"
    done

    echo "$ROW" >> "$OUTPUT_FILE"
    SAMPLE_COUNT=$((SAMPLE_COUNT + 1))

    if [ "$SAMPLE_INTERVAL" -gt 0 ]; then
        sleep $(echo "scale=3; $SAMPLE_INTERVAL / 1000" | bc)
    fi
done

END_TIME=$(get_timestamp)
TEMP_FILE=$(mktemp)
sed "s/# Duration: ${DURATION}s/# Capture End: $END_TIME\n# Duration: ${DURATION}s/" "$OUTPUT_FILE" > "$TEMP_FILE"
mv "$TEMP_FILE" "$OUTPUT_FILE"

echo ""
echo "=================================="
echo "采集完成"
echo "=================================="
echo "输出文件：$OUTPUT_FILE"
echo "开始时间：$START_TIME"
echo "结束时间：$END_TIME"
echo "总采样数：$SAMPLE_COUNT"
echo "=================================="

if [ "$SAMPLE_COUNT" -eq 0 ]; then
    echo "错误：零采样输出，视为采集失败"
    exit 2
fi

exit 0
