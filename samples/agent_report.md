# Agentic categorizer (tool-calling) — trajectories & metrics

Model: `qwen2.5:7b`. The agent gets only the job name and must call tools to find the failure itself.

## Trajectory metrics (from the real runs)
- **11/12 submitted** a verdict
- **steps-to-evidence:** 2.2 tool calls/case (avg)
- **call-error rate:** 0% (invalid tool params)
- **context efficiency:** agent pulled **1.55%** of the total log into context (33 KB of 2.1 MB)

## Accuracy on 8 labeled cases
| Approach | is_flake | category |
|---|---|---|
| agent (`qwen2.5:7b`) | 75% | 62% |
| **hybrid (heuristic→agent)** | **100%** | **88%** |

| Job | Verdict | Steps | Ctx% | Trajectory | Evidence |
|---|---|---|---|---|---|
| sys remote rootless fedo | `unknown` 🔴 | 2 | 8.46 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s |  |
| windows machine hyperv | `real_test_bug` 🔴 | 2 | 1.04 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: unable to copy from source docker://q |
| apiv2  rootless fedora-c | `unknown` 🔴 | 2 | 7.59 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | (evidence not found in log — refused) |
| windows machine hyperv | `real_test_bug` 🔴 | 2 | 0.87 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: requested number of CPUs (9999999) gr |
| macos machine applehv | `resource_exhaustion` 🟡 | 3 | 0.96 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: unable to start "8513fa8e8b20": alrea |
| sys remote root fedora-r | `infra_permission` 🟡 | 3 | 7.45 | search_log(pattern=FAIL\|panic\|Error\|not) → list_steps() → | chown: cannot access '/dev/kvm': No such fil |
| build fedora-current / l | `lint_format` 🔴 | 2 | 1.50 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | make: *** [Makefile:632: xref-helpmsgs-manpa |
| macos machine applehv | `race_condition` 🟡 | 2 | 0.57 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: 30d6e1de92e8: VM does not exist |
| sys local root fedora-pr | `real_test_bug` 🔴 | 3 | 2.77 | search_log(pattern=FAIL\|panic\|Error\|not) → search_log(pat | ok 74 [045] podman start --filter invalid-re |
| compose_v2  root fedora- | `flaky_dependency` 🟡 | 2 | 7.43 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | curl -fOSL https://github.com/lima-vm/lima/r |
| unit  root fedora-curren | `network_timeout` 🟡 | 2 | 9.81 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | W: Failed to fetch http://archive.ubuntu.com |
| int remote root fedora-r | `flaky_dependency` 🟡 | 1 | 5.34 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | E: Failed to fetch http://archive.ubuntu.com |