#!/bin/sh
# AI300 dry-run VPS 运维脚本（纸面交易实例，唯一生产单元 ai300-dry-run.service）。
#
# 用法：
#   bash scripts/vps_ops.sh <start|stop|restart|status|health|logs|tail|install-unit>
#
# 根目录由 AIBOT_ROOT 控制，默认 /root/AIBOT；所有路径都基于它，可安全用于演练机。
# 判活统一走 pgrep -f run_live_dry_run：进程由 setsid 拉起时 $! 拿到的是 wrapper PID，
# 不是真实运行 PID，用 $! 会误判存活。
#
# 日志目录：$AIBOT_ROOT/logs/<YYYY-MM>/<YYYY-MM-DD>/runtime.out.NN.log（月/日两级）。
# 逻辑变更时同步 deploy/README.md 与 docs/audit 基线。

set -u

AIBOT_ROOT="${AIBOT_ROOT:-/root/AIBOT}"
LOGS_ROOT="$AIBOT_ROOT/logs"
SERVICE="ai300-dry-run"
UNIT_NAME="$SERVICE.service"
UNIT_SRC_REL="deploy/systemd/$UNIT_NAME"
PATTERN="run_live_dry_run.py"

usage() {
    cat <<'EOF'
用法: bash scripts/vps_ops.sh <子命令>

  install-unit   拷贝 unit 到 /etc/systemd/system/ 并 daemon-reload（需 sudo）
  start          启动 ai300-dry-run
  stop           停止 ai300-dry-run
  restart        重启 ai300-dry-run
  status         systemctl status + ps + ExecMainPID 对照（可识别双实例）
  health         进程数 / 最新 runtime 日志 / cycle 计数与最近 3 条 tail
  logs           打印最新 runtime.out.*.log 路径
  tail           tail -f 最新 runtime 日志

环境变量: AIBOT_ROOT（默认 /root/AIBOT）
EOF
}

die() {
    printf 'error: %s\n' "$*" >&2
    exit 1
}

need_systemctl() {
    command -v systemctl >/dev/null 2>&1 || die "找不到 systemctl（本脚本面向 systemd 主机）"
}

list_pids() {
    # pgrep 自身不会匹配自己；fork 出来的真实 PID 与 wrapper 无关，故不依赖 $!
    pgrep -f "$PATTERN" 2>/dev/null || true
}

count_pids() {
    _pids=$(list_pids)
    if [ -z "$_pids" ]; then
        echo 0
    else
        printf '%s\n' "$_pids" | wc -l | tr -d ' '
    fi
}

latest_log() {
    # -maxdepth 3 = logs/<月>/<日>/file，排除 logs/analysis、logs/_smoke 之类旁支
    _files=$(find "$LOGS_ROOT" -maxdepth 3 -type f -name 'runtime.out.*.log' 2>/dev/null)
    [ -n "$_files" ] || return 1
    printf '%s\n' "$_files" | xargs -r ls -1t 2>/dev/null | head -n 1
}

cmd_install_unit() {
    _src="$(dirname "$0")/../$UNIT_SRC_REL"
    [ -f "$_src" ] || die "找不到单元文件: $_src"
    if [ "$(id -u)" -ne 0 ]; then
        printf '需要 root 权限，请用: sudo bash %s install-unit\n' "$0" >&2
        return 1
    fi
    need_systemctl
    cp "$_src" "/etc/systemd/system/$UNIT_NAME" || die "拷贝失败"
    systemctl daemon-reload || die "daemon-reload 失败"
    printf '已安装 %s；启用请执行: systemctl enable --now %s\n' "$UNIT_NAME" "$SERVICE"
}

cmd_start() {
    need_systemctl
    systemctl start "$SERVICE" || die "systemctl start 失败"
    printf '已请求启动 %s\n' "$SERVICE"
}

cmd_stop() {
    need_systemctl
    systemctl stop "$SERVICE" || die "systemctl stop 失败"
    printf '已请求停止 %s\n' "$SERVICE"
}

cmd_restart() {
    need_systemctl
    systemctl restart "$SERVICE" || die "systemctl restart 失败"
    printf '已重启 %s（15m 对齐模式下会睡到下一个收盘，属正常）\n' "$SERVICE"
}

cmd_status() {
    _count=$(count_pids)
    need_systemctl
    systemctl status "$SERVICE" --no-pager -l 2>&1 | head -n 25
    printf '\n--- ps (pattern=%s) ---\n' "$PATTERN"
    ps -eo pid=,etime=,args= 2>/dev/null | grep -F "$PATTERN" | grep -v grep || printf '(无匹配进程)\n'
    printf '\n--- PID 对照 ---\n'
    _main=$(systemctl show -p MainPID --value "$SERVICE" 2>/dev/null || true)
    [ -n "$_main" ] || _main=0
    printf 'ExecMainPID: %s\n' "$_main"
    printf 'pgrep 命中: %s 个 [%s]\n' "$_count" "$(list_pids | tr '\n' ' ')"
    _rc=0
    if [ "$_count" -gt 1 ]; then
        printf 'WARN: 检测到 %s 个 %s 进程，疑似双实例（手工 setsid 起的旧进程未退）\n' "$_count" "$PATTERN"
        printf '      处理: kill 掉非 ExecMainPID 的进程，再 systemctl restart %s\n' "$SERVICE"
        _rc=1
    elif [ "$_count" -eq 0 ]; then
        printf 'WARN: 没有运行中的 %s 进程\n' "$PATTERN"
        _rc=1
    else
        _pid=$(list_pids | head -n 1)
        if [ "$_main" != "0" ] && [ "$_main" != "$_pid" ]; then
            printf 'WARN: ExecMainPID(%s) 与实跑 PID(%s) 不一致：进程不是 systemd 拉起的\n' "$_main" "$_pid"
            _rc=1
        else
            printf 'OK: 单实例，pid=%s\n' "$_pid"
        fi
    fi
    return $_rc
}

cmd_health() {
    _count=$(count_pids)
    printf 'AIBOT_ROOT: %s\n' "$AIBOT_ROOT"
    printf 'processes: %s (expected 1)\n' "$_count"
    _log=$(latest_log || true)
    if [ -z "$_log" ]; then
        printf 'latest_log: <none>（未找到 %s/<YYYY-MM>/<YYYY-MM-DD>/runtime.out.*.log）\n' "$LOGS_ROOT"
        return 1
    fi
    printf 'latest_log: %s\n' "$_log"
    _cycles=$(grep -c 'AI300_DRY_RUN cycle' "$_log" 2>/dev/null || true)
    [ -n "$_cycles" ] || _cycles=0
    _last=$(grep -o 'AI300_DRY_RUN cycle [0-9]*' "$_log" 2>/dev/null | tail -n 1 || true)
    printf 'cycles_in_log: %s | %s\n' "$_cycles" "${_last:-<none>}"
    printf 'last_3_lines:\n'
    tail -n 3 "$_log" | sed 's/^/  /'
    [ "$_count" -eq 1 ] || return 1
}

cmd_logs() {
    _log=$(latest_log || true)
    [ -n "$_log" ] || die "未找到 runtime 日志（$LOGS_ROOT/<YYYY-MM>/<YYYY-MM-DD>/）"
    printf '%s\n' "$_log"
}

cmd_tail() {
    _log=$(cmd_logs) || exit 1
    tail -f "$_log"
}

[ "$#" -ge 1 ] || { usage; exit 1; }

case "$1" in
    install-unit) cmd_install_unit ;;
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_restart ;;
    status) cmd_status ;;
    health) cmd_health ;;
    logs) cmd_logs ;;
    tail) cmd_tail ;;
    -h|--help|help) usage ;;
    *)
        printf '未知子命令: %s\n\n' "$1" >&2
        usage >&2
        exit 2
        ;;
esac
