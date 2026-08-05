# Agentic categorizer (tool-calling) — trajectories & metrics

Model: `qwen2.5:7b`. The agent gets only the job name and must call tools to find the failure itself.

## Trajectory metrics (from the real runs)
- **11/12 submitted** a verdict
- **steps-to-evidence:** 1.8 tool calls/case (avg)
- **call-error rate:** 0% (invalid tool params)
- **context efficiency:** agent pulled **0.11%** of the total log into context (26 KB of 23.1 MB)

## Accuracy on 6 labeled cases
| Approach | is_flake | category |
|---|---|---|
| agent (`qwen2.5:7b`) | 100% | 33% |
| **hybrid (heuristic→agent)** | **100%** | **83%** |

| Job | Verdict | Steps | Ctx% | Trajectory | Evidence |
|---|---|---|---|---|---|
| windows machine hyperv | `unknown` 🔴 | 1 | 0.35 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | L433: Error: requested number of CPUs (99999 |
| macos machine applehv | `unknown` 🔴 | 3 | 0.93 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s |  |
| sys remote root fedora-r | `infra_permission` 🟡 | 3 | 7.45 | search_log(pattern=FAIL\|panic\|Error\|not) → list_steps() → | chown: cannot access '/dev/kvm': No such fil |
| build fedora-current / l | `lint_format` 🔴 | 2 | 1.50 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | xref-helpmsgs-manpages: 'podman build --help |
| macos machine applehv | `unknown` 🔴 | 2 | 0.57 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(e | Error: 30d6e1de92e8: VM does not exist |
| sys local root fedora-pr | `unknown` 🔴 | 2 | 1.78 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s |  |
| compose_v2  root fedora- | `unknown` 🔴 | 2 | 7.43 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | curl -fOSL https://github.com/lima-vm/lima/r |
| unit  root fedora-curren | `network_timeout` 🟡 | 1 | 3.40 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | W: Failed to fetch http://archive.ubuntu.com |
| int remote root fedora-r | `network_timeout` 🟡 | 1 | 5.34 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | E: Failed to fetch http://archive.ubuntu.com |
| macos machine applehv | `unknown` 🔴 | 2 | 0.63 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(e | /Users/MacM1-1-worker/ci/podman/podman/pkg/m |
| int local root fedora-ra | `unknown` 🔴 | 2 | 0.01 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: must specify pod value with init-ctr |
| Validate source code cha | `lint_format` 🔴 | 1 | 0.89 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | ##[error]libpod/runtime_ctr.go:12:1: File is |