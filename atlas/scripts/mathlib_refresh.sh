#!/usr/bin/env bash
# Mathlib's disk round the sun follows the Mathlib commit Tau Ceti builds on: the one in Tau Ceti's lake-manifest.json
# on its main branch. When that commit has moved since data/mathlib-pin.json, this extracts Mathlib at the new commit
# with trust-extract (about twenty minutes on a GitHub runner) and makes data/mathlib-disk.json again
# (scripts/mathlib_disk.py); otherwise it does nothing. The disk shows only what has landed in Mathlib at that commit.
# .github/workflows/tauceti-progress.yml runs it before the pages are built.
#
#   scripts/mathlib_refresh.sh WORKDIR [--force]     --force makes the disk again though the commit has not moved
set -euo pipefail
work=${1:?a working folder}
force=${2:-}
pin=$(python3 -c "import json; print(json.load(open('data/mathlib-pin.json'))['mathlib'])")
commit=$(curl -sSfL https://raw.githubusercontent.com/TauCetiProject/TauCeti/main/lake-manifest.json \
  | python3 -c "import json, sys; print(next(p['rev'] for p in json.load(sys.stdin)['packages'] if p['name'] == 'mathlib'))")
if [ "$commit" = "$pin" ] && [ "$force" != "--force" ]; then
  echo "Tau Ceti's Mathlib is still ${commit:0:12}: the disk stays as it is."
  exit 0
fi
echo "Making the Mathlib disk at ${commit:0:12} (it was made at ${pin:0:12})."
mkdir -p "$work"
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL 2> /dev/null || true
git clone -q --filter=blob:none https://github.com/leanprover-community/mathlib4 "$work/mathlib4"
git -C "$work/mathlib4" checkout -q "$commit"
if ! command -v lake > /dev/null; then
  curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none > /dev/null
  export PATH="$HOME/.elan/bin:$PATH"
fi
(cd "$work/mathlib4" && lake exe cache get > /dev/null && lake build --no-build Mathlib > /dev/null)
python3 scripts/extractor.py install "$work/mathlib4/lean-toolchain" "$work/extractor" > /dev/null
extract=$(find "$work/extractor" -type f -name trust-extract | head -1)
sudo sysctl -q -w vm.max_map_count=262144 2> /dev/null || true
(cd "$work/mathlib4" && lake env "$extract" extract --root Mathlib --repo leanprover-community/mathlib4 --out "$work/dataset" \
  --parts 8 --jobs 1 --no-statements --no-upstream-docs > /dev/null)
python3 -m venv "$work/venv"
"$work/venv/bin/pip" install -q -r requirements-data.txt
"$work/venv/bin/python" scripts/mathlib_disk.py --dataset "$work/dataset" --source "$work/mathlib4"
python3 - "$commit" "$(cat "$work/mathlib4/lean-toolchain")" << 'PY'
import json
import sys

pin = {"mathlib": sys.argv[1], "toolchain": sys.argv[2].strip(),
       "basis": "The Mathlib commit in Tau Ceti's lake-manifest.json on its main branch when scripts/mathlib_refresh.sh last made the disk."}
with open("data/mathlib-pin.json", "w", encoding="utf-8") as f:
    f.write(json.dumps(pin, indent=2) + "\n")
PY
