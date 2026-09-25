#!/usr/bin/env bash
set -euo pipefail

# Run from Ubuntu WSL: bash /mnt/c/.../sandbox_probe.sh OUTPUT_FILE
output_file="$1"
exec > "$output_file" 2>&1
printf 'probe=sandbox_probe\n'
printf 'bwrap=%s\npython=%s\ngit=%s\n' "$(bwrap --version)" "$(python3 --version)" "$(git --version)"

common=(
  --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib
  --ro-bind /lib64 /lib64 --proc /proc --dev /dev --tmpfs /tmp
  --unshare-all --die-with-parent --clearenv
  --setenv PATH /usr/bin:/bin --setenv HOME /nonexistent
  --setenv GIT_CONFIG_NOSYSTEM 1 --setenv GIT_CONFIG_GLOBAL /dev/null
)

printf '\n[host-and-network-denial]\n'
bwrap "${common[@]}" -- /usr/bin/python3 -I -B - <<'PY'
import os
import socket

host_visible = os.path.exists('/mnt/c/Windows/win.ini')
s = socket.socket()
s.settimeout(2)
network_errno = s.connect_ex(('1.1.1.1', 53))
print(f'host_file_visible={host_visible}')
print(f'network_connect_errno={network_errno}')
assert not host_visible
assert network_errno != 0
PY

probe_root=$(mktemp -d /tmp/aura-isolation-probe-XXXXXX)
printf 'probe_root=%s\n' "$probe_root"
mkdir -p "$probe_root/source" "$probe_root/outside" "$probe_root/candidate/hooks"

printf '\n[read-only-source-fsmonitor]\n'
cd "$probe_root/source"
git init -q
git config user.name Probe
git config user.email probe@example.invalid
printf 'value=1\n' > README.md
git add README.md
git commit -qm base
cat > fsmonitor.sh <<'EOF'
#!/bin/sh
echo FSMONITOR_EXECUTED >&2
printf 'effect\n' > /outside/fsmonitor-marker 2>/dev/null || true
printf 'effect\n' > /repo/source-marker 2>/dev/null || true
exit 0
EOF
chmod +x fsmonitor.sh
git add fsmonitor.sh
git commit -qm 'add fsmonitor probe'
base=$(git rev-parse HEAD)
git config core.fsmonitor /repo/fsmonitor.sh
bwrap "${common[@]}" --ro-bind "$probe_root/source" /repo -- \
  /bin/sh -c 'cd /repo; GIT_OPTIONAL_LOCKS=0 git status --porcelain' \
  > "$probe_root/fsmonitor.stdout" 2> "$probe_root/fsmonitor.stderr" || true
cat "$probe_root/fsmonitor.stdout" "$probe_root/fsmonitor.stderr"
grep -q FSMONITOR_EXECUTED "$probe_root/fsmonitor.stderr"
test ! -e "$probe_root/outside/fsmonitor-marker"
test ! -e "$probe_root/source/source-marker"
printf 'fsmonitor_invoked=yes outside_marker=no source_marker=no\n'

printf '\n[included-filter-and-hook]\n'
cd "$probe_root/candidate"
git init -q
git config user.name Probe
git config user.email probe@example.invalid
printf 'base\n' > README.md
git add README.md
git commit -qm base
printf '*.txt filter=evil\n' > .gitattributes
cat > extra-config <<'EOF'
[filter "evil"]
    clean = /repo/filter.sh
EOF
cat > filter.sh <<'EOF'
#!/bin/sh
echo FILTER_EXECUTED >&2
printf 'effect\n' > /outside/filter-marker 2>/dev/null || true
cat
EOF
cat > hooks/pre-commit <<'EOF'
#!/bin/sh
echo HOOK_EXECUTED >&2
printf 'effect\n' > /outside/hook-marker 2>/dev/null || true
exit 0
EOF
chmod +x filter.sh hooks/pre-commit
git config include.path /repo/extra-config
git config core.hooksPath /repo/hooks
bwrap "${common[@]}" --bind "$probe_root/candidate" /repo -- \
  /bin/sh -c 'cd /repo; printf "change\n" > changed.txt; git add .gitattributes changed.txt; git commit -qm candidate' \
  > "$probe_root/effects.stdout" 2> "$probe_root/effects.stderr" || true
cat "$probe_root/effects.stdout" "$probe_root/effects.stderr"
grep -q FILTER_EXECUTED "$probe_root/effects.stderr"
grep -q HOOK_EXECUTED "$probe_root/effects.stderr"
test ! -e "$probe_root/outside/filter-marker"
test ! -e "$probe_root/outside/hook-marker"
printf 'filter_invoked=yes hook_invoked=yes outside_markers=no\n'

printf '\n[fixed-unittest-exact-candidate]\n'
mkdir -p "$probe_root/proposal/tests" "$probe_root/output"
printf 'value=2\n' > "$probe_root/proposal/README.md"
cat > "$probe_root/proposal/tests/test_value.py" <<'EOF'
from pathlib import Path
import unittest

class ValueTest(unittest.TestCase):
    def test_value(self):
        self.assertEqual((Path(__file__).parents[1] / "README.md").read_text(), "value=2\n")
EOF
bwrap "${common[@]}" --ro-bind "$probe_root/source" /source \
  --ro-bind "$probe_root/proposal" /proposal --bind "$probe_root/output" /out \
  --setenv BASE "$base" -- /bin/sh -c '
    set -eu
    git clone --bare -q /source /out/repo.git
    git --git-dir=/out/repo.git worktree add --detach -q /out/worktree "$BASE"
    cp /proposal/README.md /out/worktree/README.md
    mkdir -p /out/worktree/tests
    cp /proposal/tests/test_value.py /out/worktree/tests/test_value.py
    git -C /out/worktree add README.md tests/test_value.py
    git -C /out/worktree -c core.hooksPath=/dev/null -c user.name=Probe -c user.email=probe@example.invalid commit -qm candidate
    python3 -I -B -m unittest discover -s /out/worktree/tests -p test_\*.py -v
    test -z "$(git -C /out/worktree status --porcelain)"
    git -C /out/worktree rev-parse HEAD HEAD^{tree}
  '
test -z "$(git -C "$probe_root/source" -c core.fsmonitor=false status --porcelain)"
printf 'source_clean=yes\nprobe_exit=0\n'
