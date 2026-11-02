STOP — imported US-101 map fails host validation; no placement or traffic simulation was run.

# Phase 15e retained map-stage failure — 2 November 2026

The explicit map-validity gate returned **STOP** at **14:57 Europe/London**, before the 18:00 time box. The generated map is rejected by the host with `invalid map edge endpoints, lanes, speed or length`. No importer repair, alternate clipping rule, alternate map, tree placement, baseline simulation, preregistration or score followed the failed check.

The structural inventory does retain **both US-101 directions**, **22 mainline segments** with their explicit **3–5 OSM lanes**, and **35 ramp segments** whose ends connect to retained roads or boundary cuts. These inventory checks pass, but the physical map cannot be instantiated. They do not establish a usable freeway experiment.

A read-only inspection of the rejected artifact identifies **1 unsupported self-loop edge(s)**:
- Edge 1333, OSM way 565079456, node 328 → itself; same from/to node: unsupported self-loop.

This is a failure of the new importer output at the existing host validation boundary. It is **not evidence that a freeway record beats or fails to beat eyesight**, and not a claim that the requested OSM geography is impossible to model. The failed artifact and new code are retained for review, without a post-failure repair.

The source extract is saved as `maps/us101.osm`, with SHA-256 and provenance, under the exact requested box. Caltrans demand was fixed before this check: the historical **2016** census, printed page **118**, US-101/SF postmile **2.92**, Army Street, ahead peak-hour **15,200 vehicles/hour both directions**, split equally as a stated hypothetical assumption into **7,600/hour each direction**. No traffic volume was applied in a simulation. The recency limitation and inaccessible newer sources are disclosed in `assets/phase15e/volume.json`.

The prediction and placement rule were written before any outcome in `README.md`. The first code/input commit is `f8a4f7f`; it precedes the failed map-validity run. Because step 1 fails, steps 3–4 are not attempted and no `placement.json`, traffic `validity.json`, efficacy preregistration or scores exist. The observed map-stage check is `assets/phase15e/map-validity.json`.

All existing files remain byte-identical. Default imports of both retained SF extracts compare byte for byte with unmodified-root outputs. New Python clipping tests and the isolated Rust suite pass; those tests do not erase the failed real-map check.
