# Phase 16b footage

The original file is `footage/400_SB_Crash.webm`. Its sha256 is `ab4e593ff348713a41ab341cb5fde51de8ef7f7896d139702e63ba4948df31f3`, the same digest supplied with the attachment. Width 1920, height 1080, duration 17.585 s.

| Item | As listed |
| --- | --- |
| Page | https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm |
| Author | Dash |
| Licence | Commons public-domain statement for an automated recording. Not independently adjudicated. |

The cuts below were made in this workspace with `ffmpeg -ss <start> -t <dur> -i 400_SB_Crash.webm -c:v libx264 -pix_fmt yuv420p -an`. Hashes and frame counts are in `footage/MANIFEST.json`.

| Clip | Window | What it is |
| --- | --- | --- |
| A | 11.0–14.0 s | Approach. Jackknifed trucks block the lanes ahead. |
| B | 14.5–17.5 s | SAME SOURCE, DIFFERENT VIEWPOINT. A closer stretch of this same recording. Not a second vehicle. Not an independent camera. |
| C | 0.0–5.0 s | Clear snowy highway. No jackknifed obstruction in the lanes ahead. |

## Prior acquisition stop

The previous run stopped before any of these files were in the tree. That stop, verbatim:

STOP — Phase 16b Step 1: no complete licensed footage set was acquired and visually verified in this environment. Wikimedia runtime requests were denied by the proxy (CONNECT 403), and automatic approval review rejected a subsequent access retry. Candidate licence descriptions were found, but A/B/C frames, timestamps, lane obstruction and second viewpoint remain unverified. No SAM inference, model call or merge experiment was run.

This continuation did not retry Wikimedia. The bytes above are the attached file. The earlier candidate table and the access errors remain in `search-evidence.json` and `STOP.md`.

B is one viewpoint of the file above. It is not a second car and not an independent camera.
