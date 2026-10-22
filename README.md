# Roblox DTI Halloween Minigame Bots

External **macOS** desktop automation for Dress to Impress's Tarot Cards and Apple Bobbing minigames. The programs capture screen pixels and send mouse/keyboard input. They do not inject Roblox code or read its process memory.

**Start here:** install Python → run `Setup.command` → grant Terminal permissions → calibrate Tarot → run one round before enabling replay.

These are experimental scripts, not a universal installer or a guarantee of wins. Game updates, animations, display settings, and changed UI layouts can affect recognition. Windows and Linux are not supported by the current native input code.

## What each bot does

| Bot | Behavior |
| --- | --- |
| Tarot | Reveals cards, remembers faces, prioritizes known matches, avoids pairs already confirmed unequal, and selects nearby cards to reduce pointer travel. |
| Tarot replay | Closes the reward popup, retries its close area up to three times if necessary, verifies the booth, holds E, and waits for a fresh board. There is no movement between rounds. |
| Apple Bobbing | Tracks the apple and controlled bar, holding/releasing the left mouse button to follow the target. |
| Apple replay | Uses owned Tier 1 tickets, closes confirmed rewards with retries, makes a short movement and inverse movement, then reopens the ticket inventory. It never purchases tickets. |

Apple Bobbing stops when its count-image check recognizes zero Tier 1 tickets. That check depends on the saved inventory layout; it is not a general OCR system.

## Requirements

- A Mac running Roblox and the relevant DTI minigame.
- Python **3.12 recommended**, with Tkinter for Tarot's calibration editor. The Python installer from [python.org](https://www.python.org/downloads/macos/) includes a convenient installation route. Verify Tkinter with the command below.
- An internet connection for initial Python dependency installation.
- macOS Screen Recording and Accessibility permission for **Terminal**, which runs the launchers.
- One visible Roblox window. Keep it focused and keep its size unchanged while a bot runs.

The project uses NumPy, Pillow, OpenCV, MSS, and PyObjC's Quartz/Cocoa bindings. Dependencies are listed in `requirements.txt`.

## 1. Download the repository

On GitHub, choose **Code → Download ZIP**, extract it, and move the resulting folder somewhere convenient, such as Documents. Alternatively, in Terminal:

```sh
git clone https://github.com/shrutin3009/roblox-dti-halloween-minigame-bots.git
cd roblox-dti-halloween-minigame-bots
```

Keep the folder structure intact. Apple Bobbing imports shared code from `outputs/tarot_bot`.

## 2. Install dependencies

Install Python, then double-click **Setup.command**. It creates `work/runtime` on your own computer and installs dependencies there. Do not copy another computer's virtual environment into this repository.

If Finder cannot execute the setup file, open Terminal in the extracted repository folder and run:

```sh
chmod +x Setup.command
./Setup.command
```

For manual setup:

```sh
python3.12 -m tkinter
python3.12 -m venv work/runtime
work/runtime/bin/python -m pip install --upgrade pip
work/runtime/bin/python -m pip install -r requirements.txt
chmod +x ./*.command outputs/tarot_bot/*.command outputs/apple_bobber/*.command
```

The first command should open a small Tk window. Close it before continuing. If your Python executable is named `python3`, substitute that name after confirming it is version 3.12 or newer.

## 3. Enable macOS permissions

Open **System Settings → Privacy & Security** and enable Terminal under:

1. **Accessibility** — permits simulated mouse and keyboard input.
2. **Screen Recording** (called **Screen & System Audio Recording** on some macOS versions) — permits reading Roblox pixels.

Use the **+** button to add Terminal if needed. Terminal is normally in `/Applications/Utilities/Terminal.app`. Quit and reopen Terminal after changing permissions, then relaunch the script. If macOS identifies Python separately, grant the permission to the executable it identifies as well.

If you run scripts through another terminal or editor, that host may need its own permissions. The simplest workflow is to use the supplied `.command` launchers in Terminal.

## 4. Calibrate Tarot on your laptop

Calibration is specific to your Roblox window and display. This repository intentionally excludes the original user's calibration and gameplay logs.

1. Open Roblox, go to the Tarot booth, hold E yourself, and leave a **fresh, fully face-down board** visible. The current default layout has **4 rows × 4 columns: 16 cards**.
2. Close menus and overlays that cover the cards. Set the window size you intend to use.
3. Double-click `outputs/tarot_bot/Run.command` and choose **1 — Calibrate**.
4. Click Roblox within the five-second countdown so it is foreground for capture.
5. In the calibration editor, check every numbered center. Drag centers to correct them. Press **R**, then click the first and last card centers to rebuild a regular grid if needed.
6. Press **Enter** to save, or **Escape** to cancel.
7. Check `outputs/tarot_bot/numbered-grid.png`. Centers and the card interiors must line up accurately.

Calibration records screenshot-to-window scaling for Retina displays. Do not manually divide coordinates by two. Recalibrate after changing display scaling or window size.

For a different grid, calibration accepts explicit dimensions, for example:

```sh
work/runtime/bin/python outputs/tarot_bot/tarot.py calibrate --rows 4 --cols 4
```

## 5. Run Tarot

For a first test, leave the board visible, double-click `outputs/tarot_bot/Run.command`, choose **3 — Play one round**, and focus Roblox within the countdown.

For continuous replay, double-click **Start Tarot.command** at the repository root. It activates Roblox and waits **10 seconds** before playing. Stay near the booth so E can start the next round. Keep Roblox focused throughout the session.

Unknown cards can produce initial mismatches; the solver needs to see their faces to learn them. Confirmed failed pairs are excluded for that round. Correct pairs use a shorter readiness window than incorrect pairs, which must finish flipping back. The intro-preview memorization experiment is not enabled.

If Roblox was closed and reopened, its window ID may change. With the **same window size and a fresh face-down board**, run **Reconnect Tarot Window.command**. It verifies all saved card positions against the backs before updating the window reference. If verification fails, recalibrate rather than forcing the old coordinates.

## 6. Run Apple Bobbing

Apple Bobbing has **no general-purpose interactive calibration wizard**. Its ROI, bar templates, inventory locations, and zero-ticket reference were tested against a **1000 × 697 logical-pixel Roblox window**. It is less portable than Tarot: a different layout may require updating code and reference images.

1. Match the tested window size/layout as closely as possible.
2. Stand at the Apple Bobbing station with its **E / Use Tickets** prompt visible.
3. Ensure you own Tier 1 tickets. The replay launcher will consume owned Tier 1 tickets until stopped or until it recognizes zero.
4. For observation without gameplay input, double-click `outputs/apple_bobber/Monitor.command` while an Apple round is already active. Check `monitor.png`: green should outline the controlled bar, and red should outline the apple.
5. Double-click **Start Apple Bobbing.command** for ticket use and repeat play. It waits **10 seconds**.

The gameplay input is **left mouse hold/release, not Space**. Its control point varies between rounds, while decisions follow the target's observed position. If detection is wrong, stop and fix the layout; do not leave it spending tickets unattended.

Advanced single-round launchers: `Start-Tier1.command` uses one owned ticket; `Run.command` controls an already active round. These internal Apple launchers currently use a three-second delay, unlike the root replay launcher's ten seconds.

## Stop or pause

- Press **Escape**. It can also open Roblox's menu; close that menu before restarting.
- Move the pointer to the main display's extreme top-left corner for an emergency stop.
- Use **Control-C** in the script's Terminal window.

Switching focus away from Roblox or changing its window geometry also stops input. Run only one bot at a time. The bots share a controller lock during gameplay; do not start a second controller during a replay transition.

Continuous replay means repeat while recognized states remain valid. It does not disable stop conditions or guarantee uninterrupted operation.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Nothing happens during the first ten seconds | This is the replay launcher's startup countdown. Then check the log for an actual stop reason. |
| Screen Recording permission error or blank captures | Enable permission for the terminal host, fully quit it, and reopen it. |
| Accessibility error or no mouse/keyboard response | Check Accessibility permission, foreground Roblox, and blocked system dialogs. |
| `No module named ...` or missing `work/runtime/bin/python` | Run `Setup.command` from this repository. |
| Calibration editor will not open | Check `python3.12 -m tkinter`; use a Python installation with Tk support. |
| Window ID changed | Use Reconnect Tarot Window with an unchanged size and all cards face down, or recalibrate. |
| Size/scaling changed or clicks miss card interiors | Stop and recalibrate Tarot. Apple may need its layout-specific code/reference images adjusted. |
| Another instance is running | Stop the earlier controller with Escape or Control-C. Do not delete a lock to force simultaneous input. |
| New board timeout | Verify the popup closed, E prompt is visible, menus are closed, and the station is in interaction range. |
| Reward still visible | Tarot and Apple both retry their close areas up to three times; persistent failure requires inspecting the layout. |
| Repeated recognition recovery or click retries | Stop and inspect calibration, overlays, capture quality, and animations. Logs distinguish missed clicks from uncertain recognition. |
| Apple stops at zero tickets | Expected. It does not purchase replacements. |
| macOS blocks opening a downloaded launcher | Inspect the source first and use the operating system's normal approval flow for code you trust. |

## Logs and tests

- Tarot: `outputs/tarot_bot/repeat-run.log`
- Apple: `outputs/apple_bobber/run.log`, `status.json`, and `monitor.png`
- Local timing experiments: benchmark scripts inside `outputs/tarot_bot`; they are not required for ordinary play. `loss_benchmark.py` deliberately loses rounds and should not be used to farm candy—the observed loss test did not establish any candy payout.

Offline tests do not send gameplay input:

```sh
work/runtime/bin/python -m unittest discover -s outputs/tarot_bot -p 'test_*.py'
work/runtime/bin/python -m unittest discover -s outputs/apple_bobber -p 'test_*.py'
```

Some tests use local recorded gameplay fixtures and skip when those captures are absent from a clean clone. Passing tests does not establish that a new game version or laptop layout works live.

## Repository layout

```text
Start Tarot.command
Start Apple Bobbing.command
Reconnect Tarot Window.command
Setup.command
requirements.txt
outputs/
  tarot_bot/       # Shared desktop input, Tarot code, reference images, tests
  apple_bobber/    # Tracker, inventory references, templates, tests
work/runtime/     # Created locally by Setup.command; not committed
```

## Limits

Randomized coordinates and timing do not make software indistinguishable from a person. This project has not tested Roblox's detection systems and makes no claim of avoiding detection. It also cannot guarantee every win, a fixed candy rate, or recovery from every UI change. Use it only where automation is permitted.

When opening an issue, include the bot name, macOS/Python version, window dimensions, the final log lines, and a screenshot of the relevant UI. Review screenshots and logs for personal information before sharing them.
