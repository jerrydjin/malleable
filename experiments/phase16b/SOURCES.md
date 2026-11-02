# Phase 16b footage search

STOP — Phase 16b Step 1: no complete licensed footage set was acquired and visually verified in this environment. Wikimedia runtime requests were denied by the proxy (CONNECT 403), and automatic approval review rejected a subsequent access retry. Candidate licence descriptions were found, but A/B/C frames, timestamps, lane obstruction and second viewpoint remain unverified. No SAM inference, model call or merge experiment was run.

No A, B or C clip was selected, downloaded, trimmed or inspected. Timestamps and independent-view claims remain unverified. These are candidate source-page descriptions, not experimental inputs. Full search queries, access attempts, exact original media URLs, and the automatic approval rejection are in [search-evidence.json](search-evidence.json).

| Candidate | Author as listed | Licence as listed | Timestamp selection | Finding |
| --- | --- | --- | --- | --- |
| [Dashcam video of 2012 Branson tornado damage](https://commons.wikimedia.org/wiki/File:Dashcam_vid_of_2012_Branson_tornado_damage.webm) | SvobodaKC | [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | Unselected | Source description and licence read; frames unavailable. Lane blockage and repeated viewpoint unverified. |
| [Police dashcam captures small plane crashing onto Florida road](https://commons.wikimedia.org/wiki/File:Police_Dashcam_Captures_Small_Plane_Crashing_Onto_Florida_Road.webm) | PoliceActivity | Public domain, Florida government record statement on Commons | Unselected | Source description read; frames unavailable. No A/B/C segment designated. |
| [400 SB Crash](https://commons.wikimedia.org/wiki/File:400_SB_Crash.webm) | Dash | Public-domain automated-recording statement on Commons | Unselected | Source description read; licence assertion not independently adjudicated and frames unavailable. |
| [ROAD dataset](https://github.com/gurkirt/road-dataset) | Gurkirt Singh et al.; Oxford RobotCar source | CC BY-NC-SA 4.0 | Unselected | Excluded: the noncommercial licence is outside the permitted list. |
| [RoadDamageDetector](https://github.com/sekilab/RoadDamageDetector/blob/master/README.md) | Not verified | Dataset images described as CC BY-SA 4.0 in search result | Unselected | Images do not establish usable obstruction video or a second viewpoint. |
| [SyntheticStreetScenes](https://huggingface.co/datasets/mehmetkeremturkcan/SyntheticStreetScenes) | Not verified | Search result says CC BY 4.0 | Unselected | Synthetic footage fails the real-footage requirement. |
| [Traffic surveillance video corpus](https://huggingface.co/datasets/thundarstrom/traffic-surveillance-video-corpus) | Not verified | Search result says CC BY 4.0 | Unselected | Individual provenance, obstruction and second view not verified. |

The retained [A36 photograph attribution](../../assets/phase15/ATTRIBUTION.md) names David Martin and CC BY-SA 2.0. That single still cannot establish real video or second-clip confirmation. It was not reused as footage.

Search covered Commons dashcam categories, fallen-tree/obstruction video, GitHub road-hazard video datasets, and permitted-licence alternatives. Commons runtime requests failed before an origin response, with `Tunnel connection failed: 403 Forbidden`. Thus no origin response headers or video bytes are claimed. The web tool could read source descriptions but reported unsupported `video/webm` when opening media. No proxy workaround followed the denied retry.
