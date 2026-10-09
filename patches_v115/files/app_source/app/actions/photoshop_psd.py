from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote


class PhotoshopPsdError(RuntimeError):
    pass


def _js_string(value: str) -> str:
    return (
        '"'
        + str(value)
        .replace('\\', '\\\\')
        .replace('"', '\\"')
        .replace('\r', '\\r')
        .replace('\n', '\\n')
        + '"'
    )


def _bridge_path() -> Path:
    return Path(__file__).with_name("photoshop_jsx_bridge.vbs")


def _run_jsx_text(
    jsx_text: str,
    photoshop_path: str = "",
    open_if_closed: bool = True,
    timeout: int = 90,
) -> str:
    """Run a JSX through the existing Photoshop COM bridge.

    ExtendScript runtime exceptions are not always propagated back through COM,
    so the PSD helpers below also write their own status file. This function
    validates only the bridge/COM layer.
    """
    ps = str(photoshop_path or "").strip().strip('"')
    if ps and open_if_closed:
        p = Path(ps).expanduser()
        if not p.exists():
            raise PhotoshopPsdError(f"Photoshop no existe en la ruta indicada:\n{p}")
        try:
            subprocess.Popen(
                [str(p)],
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except OSError as exc:
            raise PhotoshopPsdError(f"No se pudo abrir Photoshop:\n{exc}") from exc

    bridge = _bridge_path()
    if not bridge.exists():
        raise PhotoshopPsdError(f"Falta el puente de Photoshop:\n{bridge}")

    fd, temp_name = tempfile.mkstemp(prefix="midi_premium_psd_", suffix=".jsx")
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        temp_path.write_text(jsx_text, encoding="utf-8")
        args = [
            "cscript.exe",
            "//Nologo",
            str(bridge),
            str(temp_path),
            "1" if open_if_closed else "0",
        ]
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            raise PhotoshopPsdError("Photoshop no respondió a la operación PSD.") from exc

        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if result.returncode != 0 or not output.startswith("OK"):
            raise PhotoshopPsdError(
                error or output or "Photoshop no confirmó la operación PSD."
            )
        return output
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass


def _validate_psd(raw_path: str) -> Path:
    raw = str(raw_path or "").strip().strip('"')
    if not raw:
        raise PhotoshopPsdError("No se seleccionó ningún archivo PSD/PSB.")
    path = Path(raw).expanduser()
    if not path.exists() or path.suffix.lower() not in {".psd", ".psb"}:
        raise PhotoshopPsdError(
            f"El archivo PSD/PSB no existe o no es válido:\n{path}"
        )
    return path.resolve()


def _read_status(path: Path, fallback: str) -> list[str]:
    if not path.exists():
        raise PhotoshopPsdError(fallback)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        raise PhotoshopPsdError(fallback)
    first = lines[0]
    if first.startswith("ERROR\t"):
        message = unquote(first.split("\t", 1)[1]) if "\t" in first else fallback
        raise PhotoshopPsdError(message or fallback)
    if first != "OK":
        raise PhotoshopPsdError(first or fallback)
    return lines[1:]


def _common_js_helpers() -> str:
    # Keep this ES3-compatible. Photoshop ExtendScript is an old JavaScript engine;
    # avoid Array.map/filter, let/const, arrow functions, template strings, etc.
    return r'''
function normPath(s) {
    return String(s).replace(/\\/g, "/").toLowerCase();
}
function docFilePath(doc) {
    try { return normPath(doc.fullName.fsName); } catch (e) { return ""; }
}
function filePath(fileObj) {
    try { return normPath(fileObj.fsName); } catch (e) { return normPath(fileObj); }
}
function sameFile(doc, fileObj) {
    var a = docFilePath(doc);
    var b = filePath(fileObj);
    return a != "" && b != "" && a == b;
}
function findOpenDocument(fileObj) {
    var i;
    for (i = 0; i < app.documents.length; i++) {
        if (sameFile(app.documents[i], fileObj)) return app.documents[i];
    }
    return null;
}
function findDestinationDocument(sourceFile) {
    var active = null;
    try { active = app.activeDocument; } catch (e) {}
    if (active && !sameFile(active, sourceFile)) return active;
    var i;
    for (i = 0; i < app.documents.length; i++) {
        if (!sameFile(app.documents[i], sourceFile)) return app.documents[i];
    }
    return null;
}
function safeEncode(s) {
    try { return encodeURIComponent(String(s)); }
    catch (e) { return escape(String(s)); }
}
function errorText(e) {
    var msg = "Error de Photoshop";
    try { if (e && e.message) msg = String(e.message); else msg = String(e); } catch (x) {}
    try { if (e && e.line) msg += " (línea " + e.line + ")"; } catch (x2) {}
    return msg;
}
'''


def list_psd_elements(
    psd_path: str,
    photoshop_path: str = "",
    open_if_closed: bool = True,
) -> list[dict]:
    source = _validate_psd(psd_path)
    fd, out_name = tempfile.mkstemp(prefix="midi_premium_layers_", suffix=".txt")
    os.close(fd)
    out_path = Path(out_name)

    try:
        jsx = f'''#target photoshop
app.bringToFront();
{_common_js_helpers()}
var sourceFile = new File({_js_string(str(source))});
var outputFile = new File({_js_string(str(out_path))});
var previousDoc = null;
var sourceDoc = null;
var openedByScript = false;

function writeStatusLine(text) {{
    outputFile.encoding = "UTF8";
    if (!outputFile.opened) outputFile.open("w");
    outputFile.writeln(text);
}}
function writeElement(kind, visible, parts) {{
    var encoded = [];
    var j;
    for (j = 0; j < parts.length; j++) encoded.push(safeEncode(parts[j]));
    outputFile.writeln(kind + "\\t" + encoded.join("|"));
}}
function walk(container, parts) {{
    var i, layer, next, j, kind;
    for (i = 0; i < container.layers.length; i++) {{
        layer = container.layers[i];
        next = [];
        for (j = 0; j < parts.length; j++) next.push(parts[j]);
        next.push(layer.name);
        kind = (layer.typename == "LayerSet") ? "group" : "layer";
        writeElement(kind, layer.visible, next);
        if (layer.typename == "LayerSet") walk(layer, next);
    }}
}}

try {{
    try {{ previousDoc = app.activeDocument; }} catch (e0) {{ previousDoc = null; }}
    sourceDoc = findOpenDocument(sourceFile);
    if (!sourceDoc) {{
        sourceDoc = app.open(sourceFile);
        openedByScript = true;
    }}
    outputFile.encoding = "UTF8";
    if (!outputFile.open("w")) throw new Error("No se pudo crear el archivo temporal de capas.");
    outputFile.writeln("OK");
    walk(sourceDoc, []);
    outputFile.close();
    if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
    if (previousDoc) app.activeDocument = previousDoc;
}} catch (e) {{
    try {{ if (outputFile.opened) outputFile.close(); }} catch (close1) {{}}
    try {{
        outputFile.encoding = "UTF8";
        outputFile.open("w");
        outputFile.writeln("ERROR\\t" + safeEncode(errorText(e)));
        outputFile.close();
    }} catch (writeErr) {{}}
    try {{ if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES); }} catch (close2) {{}}
    try {{ if (previousDoc) app.activeDocument = previousDoc; }} catch (restoreErr) {{}}
}}
'''
        _run_jsx_text(jsx, photoshop_path, open_if_closed, timeout=90)
        raw_items = _read_status(
            out_path,
            "Photoshop abrió el PSD pero no pudo devolver la lista de capas/grupos.",
        )

        items: list[dict] = []
        for raw in raw_items:
            if "\t" not in raw:
                continue
            fields = raw.split("\t", 2)
            if len(fields) == 3:
                kind, visible_raw, encoded = fields
                visible = visible_raw == "1"
            else:
                kind, encoded = raw.split("\t", 1)
                visible = True
            parts = [unquote(p) for p in encoded.split("|") if p != ""]
            if parts:
                items.append(
                    {
                        "kind": kind,
                        "visible": visible,
                        "path": parts,
                        "label": " / ".join(parts),
                    }
                )
        return items
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


def insert_psd_element(
    psd_path: str,
    element_path: list[str] | tuple[str, ...],
    photoshop_path: str = "",
    open_if_closed: bool = True,
) -> None:
    source = _validate_psd(psd_path)
    parts = [str(x) for x in (element_path or []) if str(x)]
    if not parts:
        raise PhotoshopPsdError("No se seleccionó ninguna capa o grupo del PSD.")

    fd, status_name = tempfile.mkstemp(prefix="midi_premium_insert_", suffix=".txt")
    os.close(fd)
    status_path = Path(status_name)
    js_parts = ", ".join(_js_string(p) for p in parts)

    try:
        jsx = f'''#target photoshop
app.bringToFront();
{_common_js_helpers()}
var sourceFile = new File({_js_string(str(source))});
var statusFile = new File({_js_string(str(status_path))});
var sourceDoc = null;
var targetDoc = null;
var openedByScript = false;
var pathParts = [{js_parts}];

function saveStatus(ok, text) {{
    try {{
        statusFile.encoding = "UTF8";
        statusFile.open("w");
        statusFile.writeln((ok ? "OK" : "ERROR\\t" + safeEncode(text)));
        statusFile.close();
    }} catch (e) {{}}
}}
function findChild(container, name) {{
    var i;
    for (i = 0; i < container.layers.length; i++) {{
        if (container.layers[i].name == name) return container.layers[i];
    }}
    return null;
}}

try {{
    targetDoc = findDestinationDocument(sourceFile);
    if (!targetDoc) throw new Error("No hay un documento destino abierto. Abre el meme y déjalo activo antes de usar el PAD.");

    sourceDoc = findOpenDocument(sourceFile);
    if (!sourceDoc) {{
        sourceDoc = app.open(sourceFile);
        openedByScript = true;
    }}

    var current = sourceDoc;
    var found = null;
    var p;
    for (p = 0; p < pathParts.length; p++) {{
        found = findChild(current, pathParts[p]);
        if (!found) break;
        current = found;
    }}
    if (!found) throw new Error("No se encontró el elemento: " + pathParts.join(" / "));

    app.activeDocument = sourceDoc;
    found.duplicate(targetDoc, ElementPlacement.PLACEATBEGINNING);
    app.activeDocument = targetDoc;

    if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
    saveStatus(true, "");
}} catch (e) {{
    try {{ if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES); }} catch (closeErr) {{}}
    try {{ if (targetDoc) app.activeDocument = targetDoc; }} catch (restoreErr) {{}}
    saveStatus(false, errorText(e));
}}
'''
        _run_jsx_text(jsx, photoshop_path, open_if_closed, timeout=90)
        _read_status(
            status_path,
            "Photoshop no confirmó que el elemento se insertara en el documento activo.",
        )
    finally:
        try:
            status_path.unlink(missing_ok=True)
        except Exception:
            pass



def insert_psd_elements(
    psd_path: str,
    element_paths: list[list[str]] | tuple[tuple[str, ...], ...],
    photoshop_path: str = "",
    open_if_closed: bool = True,
) -> None:
    """Insert several layers/groups from one PSD into the current Photoshop document."""
    source = _validate_psd(psd_path)
    clean_paths: list[list[str]] = []
    for raw_path in element_paths or []:
        parts = [str(x) for x in (raw_path or []) if str(x)]
        if parts:
            clean_paths.append(parts)
    if not clean_paths:
        raise PhotoshopPsdError("No se seleccionó ninguna capa o grupo del PSD.")

    fd, status_name = tempfile.mkstemp(prefix="midi_premium_insert_multi_", suffix=".txt")
    os.close(fd)
    status_path = Path(status_name)
    js_arrays = []
    for parts in clean_paths:
        js_arrays.append("[" + ", ".join(_js_string(p) for p in parts) + "]")
    js_selected = ", ".join(js_arrays)

    try:
        jsx = f'''#target photoshop
app.bringToFront();
{_common_js_helpers()}
var sourceFile = new File({_js_string(str(source))});
var statusFile = new File({_js_string(str(status_path))});
var sourceDoc = null;
var targetDoc = null;
var openedByScript = false;
var selectedPaths = [{{js_selected}}];

function saveStatus(ok, text) {{
    try {{
        statusFile.encoding = "UTF8";
        statusFile.open("w");
        statusFile.writeln((ok ? "OK" : "ERROR\t" + safeEncode(text)));
        statusFile.close();
    }} catch (e) {{}}
}}
function findChild(container, name) {{
    var i;
    for (i = 0; i < container.layers.length; i++) {{
        if (container.layers[i].name == name) return container.layers[i];
    }}
    return null;
}}
function findByPath(root, pathParts) {{
    var current = root;
    var found = null;
    var p;
    for (p = 0; p < pathParts.length; p++) {{
        found = findChild(current, pathParts[p]);
        if (!found) return null;
        current = found;
    }}
    return found;
}}

try {{
    targetDoc = findDestinationDocument(sourceFile);
    if (!targetDoc) throw new Error("No hay un documento destino abierto. Abre el meme y déjalo activo antes de usar el PAD.");

    sourceDoc = findOpenDocument(sourceFile);
    if (!sourceDoc) {{
        sourceDoc = app.open(sourceFile);
        openedByScript = true;
    }}

    var i, found, pathParts;
    for (i = selectedPaths.length - 1; i >= 0; i--) {{
        pathParts = selectedPaths[i];
        found = findByPath(sourceDoc, pathParts);
        if (!found) throw new Error("No se encontró el elemento: " + pathParts.join(" / "));
        app.activeDocument = sourceDoc;
        found.duplicate(targetDoc, ElementPlacement.PLACEATBEGINNING);
    }}
    app.activeDocument = targetDoc;

    if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
    saveStatus(true, "");
}} catch (e) {{
    try {{ if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES); }} catch (closeErr) {{}}
    try {{ if (targetDoc) app.activeDocument = targetDoc; }} catch (restoreErr) {{}}
    saveStatus(false, errorText(e));
}}
'''.replace("[{js_selected}]", "[" + js_selected + "]")
        _run_jsx_text(jsx, photoshop_path, open_if_closed, timeout=90)
        _read_status(
            status_path,
            "Photoshop no confirmó que los elementos seleccionados se insertaran.",
        )
    finally:
        try:
            status_path.unlink(missing_ok=True)
        except Exception:
            pass

def insert_psd_all(
    psd_path: str,
    photoshop_path: str = "",
    open_if_closed: bool = True,
    visible_only: bool = False,
) -> None:
    source = _validate_psd(psd_path)
    visible = "true" if visible_only else "false"
    fd, status_name = tempfile.mkstemp(prefix="midi_premium_insert_all_", suffix=".txt")
    os.close(fd)
    status_path = Path(status_name)

    try:
        jsx = f'''#target photoshop
app.bringToFront();
{_common_js_helpers()}
var sourceFile = new File({_js_string(str(source))});
var statusFile = new File({_js_string(str(status_path))});
var sourceDoc = null;
var targetDoc = null;
var openedByScript = false;
var visibleOnly = {visible};

function saveStatus(ok, text) {{
    try {{
        statusFile.encoding = "UTF8";
        statusFile.open("w");
        statusFile.writeln((ok ? "OK" : "ERROR\\t" + safeEncode(text)));
        statusFile.close();
    }} catch (e) {{}}
}}

try {{
    targetDoc = findDestinationDocument(sourceFile);
    if (!targetDoc) throw new Error("No hay un documento destino abierto. Abre el meme y déjalo activo antes de usar el PAD.");

    sourceDoc = findOpenDocument(sourceFile);
    if (!sourceDoc) {{
        sourceDoc = app.open(sourceFile);
        openedByScript = true;
    }}

    app.activeDocument = sourceDoc;
    var i, layer;
    for (i = sourceDoc.layers.length - 1; i >= 0; i--) {{
        layer = sourceDoc.layers[i];
        if (!visibleOnly || layer.visible) {{
            layer.duplicate(targetDoc, ElementPlacement.PLACEATBEGINNING);
        }}
    }}
    app.activeDocument = targetDoc;

    if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES);
    saveStatus(true, "");
}} catch (e) {{
    try {{ if (openedByScript && sourceDoc) sourceDoc.close(SaveOptions.DONOTSAVECHANGES); }} catch (closeErr) {{}}
    try {{ if (targetDoc) app.activeDocument = targetDoc; }} catch (restoreErr) {{}}
    saveStatus(false, errorText(e));
}}
'''
        _run_jsx_text(jsx, photoshop_path, open_if_closed, timeout=90)
        _read_status(
            status_path,
            "Photoshop no confirmó que el contenido del PSD se insertara.",
        )
    finally:
        try:
            status_path.unlink(missing_ok=True)
        except Exception:
            pass