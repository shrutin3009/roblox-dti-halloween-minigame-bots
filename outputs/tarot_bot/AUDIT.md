# Randomness and behavior audit

The requested randomness is implemented, but **not everything is random**, and this audit cannot certify avoidance of a game's automation detector. It audits local source and simulated inputs; it does not inspect Roblox detection or enforcement.

## Results

- Sampled the actual Board.click function 10,000 times using an in-memory input driver and clock. All 10,000 sampled floating-point coordinates were different and inside the card's inset rectangle. The scheduled pause samples ranged from 0.4501 to 0.9999 seconds.
- Simulated the actual station_restart function 1,000 times with mocked visual states. All 1,000 reward-dismissal coordinates were different. All four movement directions appeared. Station waits stayed within their source ranges; movement and E key holds stayed at or below 1.18 seconds. Return direction and duration matched their required inverse.
- Nine existing tests passed, including Retina conversion, click bounds, memory solving/resuming, and reward/station recognition against captured images.
- Corrected one repeated interaction: the off-card pointer parking position now samples a random location within the window title area.

The samples used floating-point coordinates. Native display/input rounding can reuse a physical pixel, which is normal sampling behavior. Random does not mean every pixel or delay is guaranteed unique forever. The native Quartz input driver was source-reviewed but was replaced by a mock for these sample runs; these are not 11,000 live gameplay actions.

## What varies

| Behavior | Implementation |
|---|---|
| Card click position | Independent uniform x/y inside the inner 70% of the calibrated card |
| Normal gameplay click schedule | Random 0.45–1.0 seconds; readiness checks may delay the action |
| First-card pause | Random 0.1–0.6 seconds after solving starts |
| Mouse-down duration | Random 0.08–0.14 seconds |
| Off-card pointer destination | Random x within 25–75% of window width and y 6–18 logical pixels below its top |
| Reward close | Random 0.2–0.9-second pause and random point within the known close prompt |
| Movement | Random WASD direction and 0.08–0.14-second outward hold, followed by its inverse |
| Transition pauses | Randomized within the ranges shown in README.md, each below 1.2 seconds |
| E hold | Random 1.0–1.18 seconds, followed by randomized pauses and a fresh-board check |

## What remains structured

- Card selection deliberately follows an efficient memory-solving order, per the user's correction. Known matches are preferred.
- Movement returns by the opposite key for the same duration. The visual prompt verifies interaction range, not exact world coordinates.
- Pointer motion uses direct synthetic move events rather than a physical human hand trajectory. Inputs are posted through Quartz. This audit does not establish whether or how the game observes them.
- The reward → close → movement → E → solve loop repeats. Random values do not remove that overall structure.
- Screen polling, confidence thresholds, stop checks, safety timeouts, and the requested ten-second startup are fixed controls.
- Each added pause is below 1.2 seconds, but game animations, state verification, operating-system scheduling and capture latency can make actual action-to-action times longer. The complete transition is not bounded to 1.2 seconds.

These are properties of the implementation, not confirmed detector signals. A detector may use information outside the screen and input behavior audited here. There is no basis for an assurance that this automation is undetectable or safe from enforcement.

## Live-test status

A full cycle was observed in repeat-run.log: 16/16 matched, reward closed, movement and station prompt verified, E held, a fresh board confirmed, and matching started in the next round. The user subsequently pressed Escape. The newest shortened timing settings and randomized pointer parking passed offline tests but have not yet been verified through a full live cycle.

Raw sample results: randomness-audit.json.

## Subsequent pointer update

At the user’s request, title-area parking was removed after this audit. After each card click, the pointer now moves only horizontally to a random point immediately beside that card, clearing hover with no additional pause. Reward-close clicks no longer trigger a separate pointer move. The click bounds/scaling test now also checks this short local movement. The earlier title-parking description and simulation audit are historical; the latest local movement has unit coverage, not a completed live gameplay test.
