#!/bin/sh
# Render one edition and deliver it.
#   sh newsroom/publish.sh /tmp/edition.json            -> delivers to the branch "mailbox" (the Kindle reads this)
#   sh newsroom/publish.sh /tmp/edition.json rehearsal  -> delivers to another branch (the Kindle never sees it)
# Optional: NOOK_TRAILER="lines to add at the end of each commit message"
set -e
EDITION="$1"; TARGET="${2:-mailbox}"
[ -f "$EDITION" ] || { echo "usage: sh newsroom/publish.sh EDITION.json [branch]"; exit 2; }
cd "$(dirname "$0")/.."
push() { git push -q origin "$1" || git -c push.negotiate=true push -q origin "$1"; }
msg()  { if [ -n "$NOOK_TRAILER" ]; then printf '%s\n\n%s\n' "$1" "$NOOK_TRAILER"; else printf '%s\n' "$1"; fi; }

git checkout -q newsroom
python3 newsroom/render.py "$EDITION"
ID=$(sed -n 's/^id=//p' news/edition.txt)
rm -rf /tmp/news-out && cp -r news /tmp/news-out && rm -rf news

git fetch -q origin "+refs/heads/mailbox:refs/remotes/origin/mailbox"
git fetch -q origin "+refs/heads/$TARGET:refs/remotes/origin/$TARGET" 2>/dev/null || true
if git rev-parse -q --verify "origin/$TARGET" >/dev/null; then
    git checkout -q -B "$TARGET" "origin/$TARGET"
else
    git checkout -q -B "$TARGET" origin/mailbox
fi
rm -rf news && cp -r /tmp/news-out news
git add -A news
git commit -q -m "$(msg "News edition $ID")"
push "$TARGET"
git checkout -q newsroom
echo "Delivered edition $ID to branch $TARGET"
