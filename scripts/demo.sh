#!/usr/bin/env bash
# Presentation only: play committed recordings or the existing live reason board.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

print_command() {
    printf ' %q' "$@"
    printf '\n'
}

if [[ ${1:-} == --dry-run && $# == 1 ]]; then
    printf 'Shot A: saved trust loop\n'
    print_command cargo run --release -- --replay recordings/phase15a-seed1.json
    printf 'Pause: Enter closes the viewer; Enter starts the next shot.\n'
    printf 'Shot B, when BASETEN_API_KEY is nonempty: live grant/deny board\n'
    print_command cargo run --release -- --board
    printf 'Without the key: saved grant, then saved denial (pause between each)\n'
    print_command cargo run --release -- --replay recordings/grant.json
    print_command cargo run --release -- --replay recordings/deny.json
    exit 0
fi
if (( $# )); then
    printf 'Usage: bash scripts/demo.sh [--dry-run]\n' >&2
    exit 2
fi

viewer_pid=
cleanup() {
    if [[ -n $viewer_pid ]]; then
        kill "$viewer_pid" 2>/dev/null || true
        wait "$viewer_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

pause() {
    printf '%s' "$1"
    read -r || { printf '\nSTOP: terminal input closed.\n' >&2; exit 1; }
}

play() {
    printf '\n%s\n' "$1"
    shift
    print_command "$@"
    "$@" &
    viewer_pid=$!
    printf 'Press Enter here when the shot is complete to close the viewer.\n'
    # Notice failures while waiting for the presenter, without a fixed shot timer.
    while kill -0 "$viewer_pid" 2>/dev/null; do
        if read -r -t 1; then
            if kill -0 "$viewer_pid" 2>/dev/null; then
                kill "$viewer_pid" 2>/dev/null || true
                status=0
                wait "$viewer_pid" || status=$?
                viewer_pid=
                # SIGTERM is the presenter's deliberate close, not command failure.
                if (( status != 0 && status != 143 )); then
                    return "$status"
                fi
                return 0
            fi
            break
        else
            status=$?
            if (( status <= 128 )); then
                printf 'STOP: terminal input closed.\n' >&2
                return 1
            fi
        fi
    done
    status=0
    wait "$viewer_pid" || status=$?
    viewer_pid=
    return "$status"
}

play 'Shot A — replay of scored run' \
    cargo run --release -- --replay recordings/phase15a-seed1.json
pause 'Paused. Press Enter to prepare shot B. '
if [[ ${BASETEN_API_KEY:-} =~ [^[:space:]] ]]; then
    printf 'Live board: submit chest pain, then coffee before it gets cold. Inspect source/provider.\n'
    play 'Shot B — live grant/deny' cargo run --release -- --board
else
    printf 'NOTICE: BASETEN_API_KEY is absent or empty; playing recorded grant/deny, with no model calls.\n'
    play 'Shot B — recorded grant' cargo run --release -- --replay recordings/grant.json
    pause 'Paused. Press Enter to start the recorded denial. '
    play 'Shot B — recorded denial' cargo run --release -- --replay recordings/deny.json
fi
