# CI Flake Report

Analyzed **6** failed jobs — **2** look like flakes, **4** look like real failures.

| Job | Category | Flake? | Conf | Backend | Evidence |
|---|---|---|---|---|---|
| macos machine applehv | `timeout` | ✅ | 0.60 | heuristic | [FAILED] Timed out after 600.001s. |
| compose_v2  root fedora-current  ⟳re-run | `unknown` | ❌ | 0.00 | heuristic |  |
| macos machine applehv | `timeout` | ✅ | 0.60 | heuristic | [FAILED] Timed out after 600.001s. |
| Validate source code changes | `lint_format` | ❌ | 0.80 | heuristic | ##[error]libpod/runtime_ctr.go:12:1: File is not properly formatted (gofumpt) |
| windows machine hyperv | `real_test_bug` | ❌ | 0.80 | heuristic | [FAILED] failed to remove test dir: "unlinkat C:\\Users\\RUNNER~1\\AppData\\Loca |
| upgrade v5.6.2 root fedora-curre | `unknown` | ❌ | 0.00 | heuristic |  |

### macos machine applehv  (ci @ 80bf6e6)
- **Category:** `timeout` — likely flake
- **Evidence:** `[FAILED] Timed out after 600.001s.`
- **Suggested mitigation:** Operation exceeded its time budget.
- Run: https://github.com/containers/podman/actions/runs/30915761819

### compose_v2  root fedora-current / lima  (ci @ c8e8cb2)
- **Category:** `unknown` — likely real bug
- **Evidence:** ``
- **Suggested mitigation:** Manual review required.
- Run: https://github.com/containers/podman/actions/runs/30897342572

### macos machine applehv  (ci @ a25f705)
- **Category:** `timeout` — likely flake
- **Evidence:** `[FAILED] Timed out after 600.001s.`
- **Suggested mitigation:** Operation exceeded its time budget.
- Run: https://github.com/containers/podman/actions/runs/30867083551

### Validate source code changes  (ci @ 114131a)
- **Category:** `lint_format` — likely real bug
- **Evidence:** `##[error]libpod/runtime_ctr.go:12:1: File is not properly formatted (gofumpt)`
- **Suggested mitigation:** Code style/lint failure — a real change is needed, not a retry.
- Run: https://github.com/containers/podman/actions/runs/30847621165

### windows machine hyperv  (ci @ f382980)
- **Category:** `real_test_bug` — likely real bug
- **Evidence:** `[FAILED] failed to remove test dir: "unlinkat C:\\Users\\RUNNER~1\\AppData\\Local\\Temp\\podman_test3374943318\\.config\\containers\\podman\\machine\\hyperv\\a433cdae2424.lock: The process cannot acce`
- **Suggested mitigation:** A genuine test assertion/logic failure.
- Run: https://github.com/containers/podman/actions/runs/30837238524

### upgrade v5.6.2 root fedora-current / lima  (ci @ 1154b04)
- **Category:** `unknown` — likely real bug
- **Evidence:** ``
- **Suggested mitigation:** Manual review required.
- Run: https://github.com/containers/podman/actions/runs/30805471598
