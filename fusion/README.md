# SwRebuild - SolidWorks parts rebuilt in Fusion, feature by feature

A Fusion add-in that reads a part's swexport JSON (`Name.SLDPRT.json`) and remodels it the way an engineer who knows
both systems would: a new parametric design where every sketch sits on the same plane or face, with the same
geometry, the same relations and the same named driving dimensions (`Sketch1_D1`, `Boss_Extrude1_D1` ...), followed by
the features in SolidWorks' history order, driven by those parameters. SolidWorks equations become Fusion parameter
expressions; global variables become user parameters.

## Install

1. Copy the `SwRebuild` folder to Fusion's add-ins folder
   (Windows: `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns`, macOS:
   `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`), or in Fusion:
   UTILITIES > ADD-INS > Scripts and Add-Ins > Add-Ins > **+** and pick the folder.
2. Run it. **Rebuild SolidWorks Part** appears under UTILITIES > ADD-INS.

## Use - one part at a time

1. Export the part with swexport.
2. Rebuild SolidWorks Part > pick `Name.SLDPRT.json`. A new design opens.
3. After **every feature** it stops and shows what was built and what comes next:
   **Yes** = next feature, **No** = build the rest without stopping, **Cancel** = stop.
4. A log is written next to the JSON (`Name.SLDPRT.rebuild.log`): every step, and every feature or relation that
   could not be rebuilt and why.

Check each rebuilt part against the SolidWorks original (and its STEP) before relying on it.

## What v0.1 rebuilds

| SolidWorks | Fusion |
|---|---|
| Front / Top / Right planes | XY / XZ / YZ origin planes |
| offset reference planes | offset construction planes (other planes: through three points) |
| reference axes | construction axes |
| 2D sketches: lines, arcs, circles, ellipses, splines, points, construction geometry | sketch on the same plane or face |
| sketch relations (horizontal, vertical, coincident, parallel, perpendicular, tangent, concentric, equal, collinear, midpoint, symmetric, fixed) | geometric constraints |
| sketch dimensions (lengths, distances, diameters, radii, angles, offsets) | named sketch dimensions |
| boss/cut extrude: blind, mid-plane, through all, two directions, draft | extrude (join / new body / cut) |
| boss/cut revolve | revolve |
| constant-radius fillet, equal-distance chamfer | fillet, chamfer (edges matched by position) |
| Hole Wizard: simple, counterbore, countersink | hole (tapped holes at tap-drill size; thread noted in the log) |
| linear / circular pattern, mirror (of features) | rectangular / circular pattern, mirror |
| equations, global variables | parameter expressions, user parameters |

Not yet: 3D sketches, sweeps, lofts, shells, drafts, ribs, threads, thin features, up-to-surface end conditions
(cuts fall back to through-all), variable fillets, multi-body operations beyond join/new/cut, assemblies, drawings.
These are skipped with a reason in the log and the rebuild continues.

## Known approximations

* Which side a cut goes: SolidWorks' default depends on the face; if the first side removes nothing the other side
  is tried.
* Sketch regions: SolidWorks' even-odd rule (outer area solid, a loop inside it a hole, an island inside the hole
  solid) is applied to Fusion's profiles.
* Fillet, chamfer and pattern references are found by position (edge mid-points, 1 micron tolerance).
