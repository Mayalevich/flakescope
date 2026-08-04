# CI Flake Report

Analyzed **11** failed jobs — **2** flake / suspected-flake, **9** likely real or needs review.

| Job | Category | Flake status | Conf | Evidence |
|---|---|---|---|---|
| macos machine applehv | `real_test_bug` | likely real | 0.85 | [FAIL] podman machine set [It] set machine cpus, disk, memory |
| sys local root fedora-prior /  | `real_test_bug` | likely real | 0.85 | # #\| FAIL: exit code is 126; expected 0 |
| compose_v2  root fedora-curren ⟳re-run | `unknown` | needs review | 0.00 |  |
| unit  root fedora-current / li ⟳re-run | `flaky_dependency` | suspected flake | 0.80 | W: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/noble/main/binary-amd6 |
| int remote root fedora-rawhide ⟳re-run | `network_timeout` | suspected flake | 0.80 | E: Failed to fetch http://archive.ubuntu.com/ubuntu/pool/main/libc/libcacard/lib |
| macos machine applehv | `real_test_bug` | likely real | 0.85 | [FAIL] podman machine start [It] machine init --now with --update-connection |
| int local root fedora-rawhide  | `real_test_bug` | likely real | 0.85 | [FAIL] Podman run networking [It] podman run container with two static IPs one p |
| Validate source code changes | `lint_format` | likely real | 0.85 | ##[error]libpod/runtime_ctr.go:12:1: File is not properly formatted (gofumpt) |
| windows machine hyperv | `real_test_bug` | likely real | 0.85 | --- FAIL: TestMachine (2977.86s) |
| sys local root fedora-rawhide  | `unknown` | needs review | 0.00 |  |
| upgrade v5.6.2 root fedora-cur | `unknown` | needs review | 0.00 |  |

### macos machine applehv  (ci @ 80bf6e6)
- **Category:** `real_test_bug` — A genuine test assertion/logic failure.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `[FAIL] podman machine set [It] set machine cpus, disk, memory`
- Run: https://github.com/containers/podman/actions/runs/30915761819

### sys local root fedora-prior / lima  (ci @ 80bf6e6)
- **Category:** `real_test_bug` — A genuine test assertion/logic failure.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `# #| FAIL: exit code is 126; expected 0`
- Run: https://github.com/containers/podman/actions/runs/30915761819

### compose_v2  root fedora-current / lima  (ci @ c8e8cb2)
- **Category:** `unknown` — Manual review required.
- **Flake status:** needs review  (backend: heuristic)
- **Evidence:** ``
- Run: https://github.com/containers/podman/actions/runs/30897342572

### unit  root fedora-current / lima  (ci @ c8e8cb2)
- **Category:** `flaky_dependency` — External dependency/registry/mirror was unavailable.
- **Flake status:** suspected flake  (backend: heuristic)
- **Evidence:** `W: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/noble/main/binary-amd64/Packages  Connection timed out [IP: 91.189.91.82 80]`
- Run: https://github.com/containers/podman/actions/runs/30897342572

### int remote root fedora-rawhide / lima  (ci @ c8e8cb2)
- **Category:** `network_timeout` — Transient network/connectivity failure.
- **Flake status:** suspected flake  (backend: heuristic)
- **Evidence:** `E: Failed to fetch http://archive.ubuntu.com/ubuntu/pool/main/libc/libcacard/libcacard0_2.8.0-3build4_amd64.deb  Cannot initiate the connection to archive.ubuntu.com:80 (2620:2d:4002:1::103). - connec`
- Run: https://github.com/containers/podman/actions/runs/30897342572

### macos machine applehv  (ci @ a25f705)
- **Category:** `real_test_bug` — A genuine test assertion/logic failure.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `[FAIL] podman machine start [It] machine init --now with --update-connection`
- Run: https://github.com/containers/podman/actions/runs/30867083551

### int local root fedora-rawhide / lima  (ci @ a25f705)
- **Category:** `real_test_bug` — A genuine test assertion/logic failure.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `[FAIL] Podman run networking [It] podman run container with two static IPs one per subnet`
- Run: https://github.com/containers/podman/actions/runs/30867083551

### Validate source code changes  (ci @ 114131a)
- **Category:** `lint_format` — Code style/lint failure — a real change is needed, not a retry.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `##[error]libpod/runtime_ctr.go:12:1: File is not properly formatted (gofumpt)`
- Run: https://github.com/containers/podman/actions/runs/30847621165

### windows machine hyperv  (ci @ f382980)
- **Category:** `real_test_bug` — A genuine test assertion/logic failure.
- **Flake status:** likely real  (backend: heuristic)
- **Evidence:** `--- FAIL: TestMachine (2977.86s)`
- Run: https://github.com/containers/podman/actions/runs/30837238524

### sys local root fedora-rawhide / lima  (ci @ f382980)
- **Category:** `unknown` — Manual review required.
- **Flake status:** needs review  (backend: heuristic)
- **Evidence:** ``
- Run: https://github.com/containers/podman/actions/runs/30837238524

### upgrade v5.6.2 root fedora-current / lima  (ci @ 1154b04)
- **Category:** `unknown` — Manual review required.
- **Flake status:** needs review  (backend: heuristic)
- **Evidence:** ``
- Run: https://github.com/containers/podman/actions/runs/30805471598
