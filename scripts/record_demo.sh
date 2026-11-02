#!/usr/bin/env bash
# Record screen + camera (PiP) for the hackathon demo, then pick a take to submit.
#
#   ./scripts/record_demo.sh --project="DBSurgeon"
#   ./scripts/record_demo.sh --project="DBSurgeon" --pick
#   ./scripts/record_demo.sh --project="DBSurgeon" --list-devices
#
# NullMotion (https://github.com/blixvip/NullMotion) is for motion title cards /
# breakdowns — not capture. Use docs/DEMO_VIDEO.md + this script for the submit take.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="DBSurgeon"
DURATION=""
ACTION="record"
FPS=30
SCREEN_INDEX=4
CAM_INDEX=0
MIC_INDEX=1
CAM_WIDTH=360
AUTO_YES=0

usage() {
  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project=*) PROJECT="${1#*=}"; shift ;;
    --project) PROJECT="$2"; shift 2 ;;
    --duration=*) DURATION="${1#*=}"; shift ;;
    --duration) DURATION="$2"; shift 2 ;;
    --screen=*) SCREEN_INDEX="${1#*=}"; shift ;;
    --cam=*) CAM_INDEX="${1#*=}"; shift ;;
    --mic=*) MIC_INDEX="${1#*=}"; shift ;;
    --yes|-y) AUTO_YES=1; shift ;;
    --pick) ACTION="pick"; shift ;;
    --list-devices) ACTION="devices"; shift ;;
    --test) ACTION="test"; DURATION="${DURATION:-5}"; AUTO_YES=1; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

OUT_DIR="$ROOT/.local/demo_video/$PROJECT"
mkdir -p "$OUT_DIR"
SUBMIT="$OUT_DIR/submit.mp4"

list_devices() {
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 | sed -n '/AVFoundation/,/Error opening/p' | sed '$d'
}

if [[ "$ACTION" == "devices" ]]; then
  list_devices
  exit 0
fi

if [[ "$ACTION" == "pick" ]]; then
  shopt -s nullglob
  takes=("$OUT_DIR"/take-*.mp4)
  if ((${#takes[@]} == 0)); then
    echo "No takes in $OUT_DIR — record first." >&2
    exit 1
  fi
  echo "Takes for $PROJECT:"
  i=1
  for t in "${takes[@]}"; do
    sz=$(du -h "$t" | awk '{print $1}')
    echo "  [$i] $(basename "$t")  $sz"
    i=$((i + 1))
  done
  printf "Choose take number to submit [1-%d]: " "$((i - 1))"
  read -r choice
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || ((choice < 1 || choice >= i)); then
    echo "Invalid choice." >&2
    exit 1
  fi
  chosen="${takes[$((choice - 1))]}"
  ln -sfn "$(basename "$chosen")" "$SUBMIT"
  # Also copy a flat file judges can upload without resolving symlinks
  cp -f "$chosen" "$OUT_DIR/${PROJECT}_submission.mp4"
  echo "Selected → $SUBMIT"
  echo "Upload file → $OUT_DIR/${PROJECT}_submission.mp4"
  open -R "$OUT_DIR/${PROJECT}_submission.mp4" 2>/dev/null || true
  exit 0
fi

if ! command -v ffmpeg >/dev/null; then
  echo "ffmpeg required (brew install ffmpeg)" >&2
  exit 1
fi

n=1
while [[ -e "$OUT_DIR/take-$(printf '%02d' "$n").mp4" ]]; do
  n=$((n + 1))
done
TAKE="$OUT_DIR/take-$(printf '%02d' "$n").mp4"
LOG="$OUT_DIR/take-$(printf '%02d' "$n").log"

cat <<EOF

DBSurgeon demo recorder
  project : $PROJECT
  take    : $(basename "$TAKE")
  screen  : AVFoundation index $SCREEN_INDEX
  camera  : AVFoundation index $CAM_INDEX (PiP ${CAM_WIDTH}px)
  mic     : AVFoundation index $MIC_INDEX
  script  : $ROOT/docs/DEMO_VIDEO.md

Before you hit enter:
  1. Open http://127.0.0.1:3100/demo  and  /research  in Chrome
  2. Put the teleprompter (docs/DEMO_VIDEO.md) on a second display or half-screen
  3. Grant Screen Recording + Camera + Microphone if macOS prompts
  4. Speak the three beats: Problem → Tech stack → Live demo + code

EOF

if [[ "$ACTION" == "test" ]]; then
  echo "Permission probe — ${DURATION:-5}s screen+cam capture"
fi

if [[ "$AUTO_YES" -ne 1 ]]; then
  echo "Press ENTER to start recording (Ctrl+C stops)…"
  read -r _
fi

DUR_ARGS=()
if [[ -n "$DURATION" ]]; then
  DUR_ARGS=(-t "$DURATION")
  echo "Auto-stop after ${DURATION}s"
else
  echo "Recording… Ctrl+C when done."
fi

# Screen + mic on input 0; camera-only on input 1; overlay cam bottom-right.
set +e
ffmpeg -y \
  -f avfoundation -framerate "$FPS" -capture_cursor 1 -i "${SCREEN_INDEX}:${MIC_INDEX}" \
  -f avfoundation -framerate "$FPS" -video_size 1280x720 -i "${CAM_INDEX}" \
  "${DUR_ARGS[@]}" \
  -filter_complex "[1:v]scale=${CAM_WIDTH}:-1,format=yuv420p[cam];[0:v]format=yuv420p[bg];[bg][cam]overlay=W-w-24:H-h-24:format=auto" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k -ar 48000 -ac 1 \
  -movflags +faststart \
  "$TAKE" 2>"$LOG"
status=$?
set -e

if [[ $status -ne 0 && $status -ne 255 ]]; then
  echo "Recording failed (exit $status). Log: $LOG" >&2
  echo "---" >&2
  tail -30 "$LOG" >&2
  echo "---" >&2
  echo "Tip: run ./scripts/record_demo.sh --list-devices and adjust --screen/--cam/--mic" >&2
  echo "macOS: System Settings → Privacy → Screen Recording / Camera / Microphone → allow Terminal (or Cursor)." >&2
  exit $status
fi

echo
echo "Saved $TAKE"
echo "Review in QuickTime, then pick a take:"
echo "  ./scripts/record_demo.sh --project=\"$PROJECT\" --pick"
open -R "$TAKE" 2>/dev/null || true
