# Master your skills

A kids' curriculum station that teaches how AI "sees" people. A group of
adventurers lines up in front of a camera, a random pose code is generated,
and each adventurer must hold their assigned pose until the whole team goes
green and the countdown completes.

Built on [MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker)
(multi-person mode). Two implementations share the same rules and tuning:

- **Python desktop app** (this repo root) - OpenCV window, for a dedicated
  station machine. Reference implementation.
- **Web app** (`docs/`) - zero-install, runs fully in the browser via
  MediaPipe Tasks for Web. Hosted on GitHub Pages:
  **<https://ystimokk.github.io/pose-trial-game/>**. All processing stays
  on-device; no video ever leaves the browser.

## How a trial works

1. The admin starts the app with the number of participants `n` (max 5).
2. A random pose code of length `n` is generated from the letters A–D.
3. The screen asks the adventurers to line up. Once `n` people are in view,
   it announces "Detected n adventurers... Starting the trial."
4. The pose code is shown. Letters map to participants **left to right** as
   seen on screen. Each letter (and a letter above each person's head) turns
   **green** when that person holds their pose well enough, **dark red**
   otherwise. No boxes or confidence numbers are shown.
5. When every letter is green, a fading 5→1 countdown runs. If anyone breaks
   their pose — even momentarily — the countdown resets. (A grace period for
   detection flicker can be re-enabled via `break_grace_seconds` in config.)
6. Completing round 1 unlocks **round 2** with harder poses (E-H): a new code
   is generated and the trial continues.
7. Completing round 2 unlocks the **mystery round**: each adventurer gets a
   secret pose (drawn from all of A-H) that is never shown. Instead, everyone
   sees their own skeleton with each limb colored green or red, and solves
   their pose by trial and error. Circles replace the letters: red while
   searching, a personal fading countdown while holding a found pose, and
   green once the individual 5-second hold completes - that person is then
   locked in. All circles green ends the mission.
8. On clearing all rounds: "Mission complete: adventurers have mastered the
   required skill."

## The poses

Every pose is deliberately compact. The camera has to fit up to five kids
side by side, so no pose asks for a limb held out sideways: arms go up or stay
tucked, and stances stay near shoulder width. Each pose fits in roughly 1.3
torso-lengths of floor width, where a kid standing still already takes 0.75.

Round 1:

| Letter | Pose |
| --- | --- |
| A | Crane guard: forearms straight up with both fists beside the face, elbows tucked in, left knee raised and bent |
| B | Tilted X: left arm on a diagonal, right arm straight up, right leg slightly raised |
| C | Squat down with both arms reaching forward |
| D | Frog: crouch all the way down, knees pushed out past the feet, both hands to the floor |

Round 2 (harder - balance and coordination):

| Letter | Pose |
| --- | --- |
| E | Rocket: one arm shot straight up past the head, the other pressed down against the side, feet together |
| F | Tree: one foot against the other knee, arms overhead with hands together |
| G | Archer: bow arm aimed up at the sky, other elbow bent pulling the wrist to the chin, one leg lifted (either leg) |
| H | Knee hug: pull one knee to the chest with both hands while standing tall |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The pose model (~9 MB) is downloaded automatically to `models/` on first run.

## Running the station

```bash
python main.py --participants 3
```

If `--participants` is omitted, the admin is prompted for it. `--camera N`
selects a different camera when the default one is not the one pointing at the
station (see [Camera troubleshooting](#camera-troubleshooting)).

For testing poses, dev mode cycles the code through A-H in order and
auto-advances a few seconds after each completion (no lineup or rounds
between trials):

```bash
python main.py --participants 1 --dev
```

Keys while running: `i` toggles the "How to play" overlay (rules plus a
stick-figure diagram of each pose), `h` toggles hint mode (the skeleton trace
the AI detects - during the trial each limb is individually colored green or
red so participants can see exactly which body part needs fixing), `r`
regenerates the code and restarts the trial, `q` quits.

## Running the web version

Open <https://ystimokk.github.io/pose-trial-game/> (or serve `docs/` locally
with any static server, e.g. `python -m http.server --directory docs`). The
admin picks the number of adventurers on the start screen; the "Advanced"
section offers dev mode and a starting round. On-screen buttons or the same
`I` / `H` / `R` keys control the info overlay, hint trace, and new code.

The web app needs HTTPS (or localhost) for camera access - GitHub Pages
provides this automatically. Parameters live in `docs/js/config.js`,
mirroring the Python config.

## Camera troubleshooting

A camera that is covered, already in use, or blocked by the OS does not throw
an error - it quietly hands back frames that are entirely black, so the app
looks like it started fine but shows nothing. Both versions now detect this
and put a warning on screen after a couple of seconds instead of leaving you
guessing.

If the picture is black:

- **Another app or tab has the camera.** Zoom, Photo Booth, Teams, or a second
  tab of this game will do it. Quit them, then start the trial again.
- **The wrong camera got picked.** On a Mac an iPhone can register itself as a
  Continuity Camera and be chosen by default; if it is face-down or locked the
  feed is black. In the web version choose the right one from the **Camera**
  dropdown on the start screen. For the Python version:

```bash
python main.py --list-cameras     # shows which indices give a real picture
python main.py --camera 1         # then use the one that works
```

- **The OS is blocking it.** On macOS the terminal app you launch from needs
  its own camera permission (System Settings > Privacy & Security > Camera);
  without it AVFoundation returns black frames rather than failing. Browsers
  need the site allowed under the padlock icon in the address bar.

## Tuning per build

All numeric parameters live in `pose_trial/config.py`:

- `AppConfig` — gameplay values: confidence threshold (default **0.85**, with
  per-pose overrides in `confidence_overrides`, e.g. D at 0.80),
  hold duration (default **5 s**), the break grace period (default **0 s**),
  max participants (default **5**), the round alphabets, flow timings, camera
  settings, and mirror display.
- `PoseTuning` — geometry tolerances for each pose scorer (angle bands,
  distance margins). Tighten these for an older group, loosen further for
  very young kids. These bands also control how much floor space a pose
  needs: widening an arm-angle band lets kids sprawl, which means fewer of
  them fit in frame.

Only `n` is dynamic; everything else is fixed per build via `config.py`.

### Difficulty

The defaults are deliberately forgiving so kids succeed rather than fight the
detector: each pose has wide "ideal" bands that score a full 1.0 and the bar to
turn green is 85%. The bands are still narrow enough that each pose only
matches itself — the closest any wrong pose comes to passing is 0.81 against
an 0.85 bar.

Forgiveness lives in the pose geometry, not in the timer. The hold countdown
only advances on frames where every letter is green, so a red letter always
stops the clock; at the default `break_grace_seconds` of 0 it resets outright.
What keeps a letter from flickering is the size of the passing region: on the
tightest pose a single joint can drift about 0.34 torso-lengths (roughly 17 cm
on a kid) before the pose goes red, and most poses allow 0.5 or more.

To make it harder, raise `confidence_threshold` (0.95+ feels strict) and/or
narrow the ideal bands in `PoseTuning`. To give kids more physical slack,
widen the ideal bands and push the matching zero points further out — lowering
the threshold alone tends to create collisions between poses instead.
