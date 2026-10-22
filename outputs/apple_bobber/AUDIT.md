# Apple Bobbing audit — current code

## Verified evidence
The observed session won three rounds. It automatically restarted after the first two. On the third, the saved screenshot shows +200 Money and +400 Candy, but confetti obscured reward recognition and the controller stopped. A six-second recognition retry was subsequently added. Eleven component tests pass. The retry and varied gameplay hold position have not yet been tested live.

## What varies
Tier 1 button coordinates; E hold duration; pause before ticket selection; reward-close delay and coordinates within the close prompt; movement direction and short duration; movement pauses; gameplay hold position selected once per round. The pointer stays at that selected gameplay position during that round's hold/release events.

## What remains structured
The same close → movement → inverse movement → E → Tier 1 → game sequence repeats. Controller decisions follow fixed pixel tracking rules. Sampling uses a fixed requested 25 ms pause (actual intervals also depend on processing). Continuous holds are interrupted at 1.1 seconds with a requested 35 ms release. Return movement mirrors the outward duration. The program generates native synthetic mouse and keyboard events. These are code observations, not evidence of which signals Roblox monitors.

## Reliability findings
Reward recognition can be obscured by confetti; retries now reduce this failure but the transition still performs a separate single reward check. Opposite movement does not guarantee exact return because of collision, camera, and input timing effects. Inventory/button locations rely on a calibrated layout; a changed game layout may invalidate them. The shared controller lock is held during each round, but not through the between-round transition. Startup exceptions can leave a stale PID file. These are reliability limits, not confirmed detection mechanisms.

## Stop and ticket behavior
Before a Tier 1 click the script recognizes inventory and compares its count lettering against a recorded zero-count reference. A zero match stops without buying tickets. Zero recognition passes a fixture test but is not yet verified against a live depleted Tier 1 inventory. One ticket click is issued per attempt. Lost focus, moved window, Escape, the top-left emergency pointer position, or an uncertain result stops control. No auto-purchase is implemented.

## Detection conclusion
This program remains automation. Varying timing and coordinates does not establish human behavior or immunity from detection. Roblox detection internals and account-side signals were not available for this audit. No detector was tested and no claim of undetectability or guaranteed wins is supported. This audit does not recommend changes to evade detection.
