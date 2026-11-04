# Phase 16d held-out test clip: preregistration

Written 2026-11-03, before SAM or any other detector or model has been run on this footage. Until the single scored run, nobody runs SAM or any detector on this file or anything cut from it. That includes the 16d code.

## Selection rule (fixed before any candidate was looked at)
1. Licence is PD, CC0, CC BY or CC BY-SA, from Wikimedia Commons or another source with an explicit licence page.
2. Forward-facing vehicle camera on a road.
3. A physical obstruction blocks at least one lane and stays continuously in view for at least 6 s while the camera approaches.
4. There is a clear stretch of at least 3 s with no obstruction in the lane.
5. Candidates are judged only by eye on raw frames (ffmpeg contact sheets). No SAM or detector run on any candidate.

## Source
- URL: https://commons.wikimedia.org/wiki/File:Момент_массового_ДТП_с_опрокидыванием_грузовика_попал_на_видео_в_Воронеже.webm
- Author: BloknotVrn36 (YouTube video 5YAx6bRdEk8), uploaded to Commons on 2023-07-31.
- Licence: CC BY 3.0, via the {{YouTube CC-BY|BloknotVrn36}} template. The Commons {{LicenseReview}} is still pending. Attribution: "BloknotVrn36, CC BY 3.0, via Wikimedia Commons".
- File: voronezh.webm, VP9, 1280x720, 30 fps, 54.18 s, 4,741,358 bytes.
- sha256: ccc4bdf7e50345862001e4af5e1615de16c1ced7929d9ce978033ffdf49a37e3 (the Commons sha1 527fcddb2f6220d2d18bf4d17ebfd19965f69975 matches the download).

## Test input
- clip_T.mp4 is cut with `ffmpeg -ss 17.0 -t 30 -i voronezh.webm -c:v libx264 -pix_fmt yuv420p -an clip_T.mp4`
- It is 1280x720, 30 fps, 900 frames, 5,364,174 bytes, sha256 13b0533b7c39f3aafe9c8a49b5fce5c4b5c0a8d57eb0aa274a0c138d8c093704.
- Clip time t_clip = source time - 17.0 s.

## Expected ground truth (judged by eye on raw frames only)
- Stopped object: an overturned truck cargo body lying in the camera's carriageway ahead, with debris around it. It does not move relative to the road.
- Lane: the travel lanes ahead of the camera, on the camera's side of the double centre line, roughly in the middle of the camera's path.
- In view and stationary: source 27.0 s to 45.5 s, which is clip 10.0 s to 28.5 s, while the camera approaches. It leaves the frame on the left at about source 46 s.
- Clear stretch: source 17.0 s to 20.0 s (clip 0.0 s to 3.0 s), with no obstruction in the lane. Only distant moving traffic is visible.
- Moving traffic: the other vehicles moving relative to the road, including a damaged car that moves through the scene in front of the camera before and early in the truck window, plus oncoming and same-direction traffic.

## PASS rule (one run, frozen code)
The frozen 16d code is run exactly once on clip_T.mp4. Pin the commit SHA and config here before running: `16d commit = d0fcc110e5b5b03b127016270a87c483ee561d77`. All three conditions must hold:
1. **Hit:** at least one emitted edit or flag is for the overturned truck body, with a timestamp in clip 10.0 s to 28.5 s. "For" means its mask or box is mostly on the truck body, judged by eye on the frame it refers to.
2. **No moving-traffic false positives:** no edit anywhere in the clip is for a vehicle that is moving relative to the road.
3. **Clear stretch quiet:** no edit has a timestamp in clip 0.0 s to 3.0 s.

Other stationary objects (amended before lock, per Paul):
- A stopped object off the travel lanes (kerb, shoulder) is allowed only if its edit is labelled shoulder or kerb. If any such object's edit is labelled as a blocked travel lane, the run FAILS (a false lane hazard is the worst error for every car behind).
- Any other object genuinely stopped in a travel lane (e.g. other wrecks or debris from the pile-up) counts as correct, not against PASS.

Anything else is a FAIL. That includes a crash, no output, or a hit that only falls outside the window. The result is reported as is, with no reruns, retuning or window changes after the run.

## Relationship to earlier phases
- Clip 1 (Commons 400_SB_Crash.webm) failed Phase 16b bar a. That FAIL stays reported.
- The Phase 16b rule file is experiments/phase16b/prereg.md on origin/phase-16-live-sam, commit bb36299. Its sha256 is b518b7e181bbab396d575eb19fbcdc29a6980b96d1ced73a6b890926f2b76ccd. That does **not** match the fb662e62…6869df hash supplied in the brief.
- clip_A/B/C.mp4 (source 27.0/38.0/17.0 s, 3 s each) were cut for the earlier 16b-style plan. They are not part of this 16d test.
