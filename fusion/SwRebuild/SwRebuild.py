"""SwRebuild - rebuild a SolidWorks part in Fusion from its swexport JSON, one feature at a time.

Adds "Rebuild SolidWorks Part" to UTILITIES > ADD-INS. It asks for a part's .SLDPRT.json (written by swexport),
creates a new parametric design, and rebuilds the features in history order. By default it pauses after every
feature so the result can be checked; a log is written next to the JSON (<name>.rebuild.log).
"""
import os
import traceback

import adsk.core
import adsk.fusion

from .lib import rebuild

CMD_ID = "swRebuildPart"
CMD_NAME = "Rebuild SolidWorks Part"
PANEL_ID = "SolidScriptsAddinsPanel"
_handlers = []


def run(context):
    try:
        ui = adsk.core.Application.get().userInterface
        cmd = ui.commandDefinitions.itemById(CMD_ID) or ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, "Rebuild a SolidWorks part from swexport JSON, feature by feature")
        h = _Created()
        cmd.commandCreated.add(h)
        _handlers.append(h)
        panel = ui.allToolbarPanels.itemById(PANEL_ID)
        if panel and not panel.controls.itemById(CMD_ID):
            panel.controls.addCommand(cmd)
    except Exception:
        adsk.core.Application.get().userInterface.messageBox("SwRebuild failed to start:\n" + traceback.format_exc())


def stop(context):
    ui = adsk.core.Application.get().userInterface
    panel = ui.allToolbarPanels.itemById(PANEL_ID)
    if panel and panel.controls.itemById(CMD_ID):
        panel.controls.itemById(CMD_ID).deleteMe()
    cmd = ui.commandDefinitions.itemById(CMD_ID)
    if cmd:
        cmd.deleteMe()


class _Created(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        h = _Execute()
        args.command.execute.add(h)
        _handlers.append(h)


class _Execute(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            rebuild_one()
        except Exception:
            adsk.core.Application.get().userInterface.messageBox("SwRebuild error:\n" + traceback.format_exc())


def _profile_path(ui):
    """Company profile location, remembered in profile_path.txt next to the add-in (asked once)."""
    here = os.path.dirname(os.path.abspath(__file__))
    store = os.path.join(here, "profile_path.txt")
    if os.path.exists(store):
        p = open(store, encoding="utf-8").read().strip()
        if os.path.exists(p):
            return p
    dlg = ui.createFileDialog()
    dlg.title = "Company profile (profile.json) - Cancel to rebuild without one"
    dlg.filter = "Company profile (*.json)"
    if dlg.showOpen() != adsk.core.DialogResults.DialogOK:
        return None
    with open(store, "w", encoding="utf-8") as f:
        f.write(dlg.filename)
    return dlg.filename


def rebuild_one():
    app = adsk.core.Application.get()
    ui = app.userInterface
    dlg = ui.createFileDialog()
    dlg.title = "SolidWorks part export (.SLDPRT.json)"
    dlg.filter = "swexport JSON (*.json)"
    if dlg.showOpen() != adsk.core.DialogResults.DialogOK:
        return
    path = dlg.filename
    doc = rebuild.load_json(path)
    if (doc.get("document") or {}).get("type") != "part":
        ui.messageBox("This is not a part export. Only parts can be rebuilt (assemblies and drawings: later).")
        return

    log_path = os.path.splitext(path)[0] + ".rebuild.log"
    log_file = open(log_path, "w", encoding="utf-8")

    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()

    fdoc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    name = (doc.get("source") or {}).get("file") or "SolidWorks part"
    try:
        fdoc.name = os.path.splitext(name)[0]
    except Exception:
        pass

    rb = rebuild.Rebuilder(doc, design, log)
    steps = rb.steps()
    log(f"Rebuilding {name}: {len(steps)} features")
    step_mode = True
    for i, f in enumerate(steps):
        status = rb.build(f)
        log(f"[{i + 1}/{len(steps)}] {status}")
        adsk.doEvents()
        app.activeViewport.refresh()
        if step_mode and i + 1 < len(steps):
            nxt = steps[i + 1]
            r = ui.messageBox(
                f"{status}\n\nNext: {nxt.get('name')} ({nxt.get('type')})\n\n"
                "Yes = build the next feature\nNo = build all remaining features\nCancel = stop here",
                f"SwRebuild - step {i + 1} of {len(steps)}",
                adsk.core.MessageBoxButtonTypes.YesNoCancelButtonType)
            if r == adsk.core.DialogResults.DialogCancel:
                log("stopped by user")
                break
            if r == adsk.core.DialogResults.DialogNo:
                step_mode = False
    rb.finish()
    rebuild.apply_profile(rb, rebuild.load_profile(_profile_path(ui)), log)
    log(f"done: {len(rb.built)} built, {len(rb.skipped)} skipped")
    for n, t, why in rb.skipped:
        log(f"  skipped {n} ({t}): {why}")
    log_file.close()
    ui.messageBox(f"{len(rb.built)} features built, {len(rb.skipped)} skipped.\n\nLog: {log_path}", "SwRebuild")
