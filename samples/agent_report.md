# Agentic categorizer (tool-calling) — trajectories & metrics

Model: `qwen2.5:7b`. The agent gets only the job name and must call tools to find the failure itself.

## Trajectory metrics (from the real runs)
- **11/12 submitted** a verdict
- **steps-to-evidence:** 2.1 tool calls/case (avg)
- **call-error rate:** 0% (invalid tool params)
- **context efficiency:** agent pulled **1.39%** of the total log into context (30 KB of 2.1 MB)

## Accuracy on 8 labeled cases
| Approach | is_flake | category |
|---|---|---|
| agent (`qwen2.5:7b`) | 75% | 50% |
| **hybrid (heuristic→agent)** | **100%** | **88%** |

| Job | Verdict | Steps | Ctx% | Trajectory | Evidence |
|---|---|---|---|---|---|
| sys remote rootless fedo | `unknown` 🔴 | 2 | 8.46 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s |  |
| windows machine hyperv | `lint_format` 🔴 | 2 | 1.04 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | scp: dest open "directory/": Failure |
| apiv2  rootless fedora-c | `unknown` 🔴 | 2 | 7.59 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(e |  |
| windows machine hyperv | `resource_exhaustion` 🟡 | 1 | 0.35 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | Error: requested number of CPUs (9999999) gr |
| macos machine applehv | `race_condition` 🟡 | 3 | 0.96 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: unable to start "m2-504ab31298de": m1 |
| sys remote root fedora-r | `infra_permission` 🟡 | 4 | 8.52 | search_log(pattern=FAIL\|panic\|Error\|not) → search_log(pat | chown: cannot access '/dev/kvm': No such fil |
| build fedora-current / l | `lint_format` 🔴 | 2 | 1.50 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | make: *** [Makefile:632: xref-helpmsgs-manpa |
| macos machine applehv | `real_test_bug` 🔴 | 2 | 0.49 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(s | Error: 395bf3b365ff: VM does not exist |
| sys local root fedora-pr | `real_test_bug` 🔴 | 3 | 2.77 | search_log(pattern=FAIL\|panic\|Error\|not) → search_log(pat | ok 145 [150] podman push fail in 295ms |
| compose_v2  root fedora- | `flaky_dependency` 🟡 | 2 | 7.43 | search_log(pattern=FAIL\|panic\|Error\|not) → read_section(e | curl -fOSL https://github.com/lima-vm/lima/r |
| unit  root fedora-curren | `flaky_dependency` 🟡 | 1 | 3.40 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | W: Failed to fetch http://archive.ubuntu.com |
| int remote root fedora-r | `network_timeout` 🟡 | 1 | 5.34 | search_log(pattern=FAIL\|panic\|Error\|not) → submit | E: Failed to fetch http://archive.ubuntu.com |