#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${1:-assets/img}"

if ! command -v exiftool >/dev/null 2>&1; then
  echo "exiftool is required but was not found."
  exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "Image directory not found: $TARGET_DIR"
  exit 0
fi

echo "Stripping image metadata in: $TARGET_DIR"

mapfile -d '' IMAGE_FILES < <(
  find "$TARGET_DIR" -type f \( \
    -iname '*.jpg' -o \
    -iname '*.jpeg' -o \
    -iname '*.png' -o \
    -iname '*.webp' \
  \) -print0
)

if [ "${#IMAGE_FILES[@]}" -eq 0 ]; then
  echo "No JPG, PNG, or WebP files found to strip."
  exit 0
fi

exiftool -overwrite_original -all= "${IMAGE_FILES[@]}"

echo "Metadata stripped from ${#IMAGE_FILES[@]} image file(s)."
