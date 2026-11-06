#!/usr/bin/env bash
# Encode rendered frames + the mastered soundtrack into the final film, then
# make the review sheets. Run from the repo root:
#   bash trailer/src/mux.sh 16x9      (or 9x16)
set -euo pipefail
FMT="${1:-16x9}"
T=trailer
FRAMES="$T/frames/$FMT"
OUT="$T/out/moodmix-trailer-$FMT.mp4"
mkdir -p "$T/out" "$T/reviews"

n=$(ls "$FRAMES"/*.jpg | wc -l)
EXPECT="${EXPECT:-909}"
if [ "$n" -ne "$EXPECT" ]; then echo "expected $EXPECT frames in $FRAMES, found $n" >&2; exit 1; fi

ffmpeg -v error -y -framerate 30 -i "$FRAMES/%04d.jpg" -i "$T/audio/soundtrack.wav" \
  -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -profile:v high -movflags +faststart \
  -c:a aac -b:a 256k -ar 48000 -shortest "$OUT"

# poster frame: the closing title, fully drawn
cp "$FRAMES/0880.jpg" "$T/out/moodmix-trailer-$FMT-poster.jpg"

# review sheets (1 fps contact sheet + phone-size sheet)
ffmpeg -v error -y -i "$OUT" -vf "fps=1,scale=320:-1,tile=6x6" -frames:v 1 "$T/reviews/contact-$FMT.png"
ffmpeg -v error -y -i "$OUT" -vf "fps=1/3,scale=200:-1,tile=9x1" -frames:v 1 "$T/reviews/phone-$FMT.png"

ffprobe -v error -show_entries stream=codec_name,width,height,avg_frame_rate,duration -of json "$OUT"
