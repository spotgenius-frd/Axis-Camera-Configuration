"""
Parse Axis param.cgi listdefinitions XML into normalized metadata.
Provides current value, writability, type, and allowed choices/ranges per parameter.
"""

import xml.etree.ElementTree as ET
from typing import Any


# Axis schema namespace (optional; some cameras omit it)
NS = "http://www.axis.com/ParameterDefinitionsSchema"


def _local_tag(tag: str) -> str:
    """Strip namespace from tag for matching."""
    if tag.startswith("{") and "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _is_writable(security_level: str, type_elem: ET.Element | None) -> bool:
    """
    Security level is 4 digits: create, delete, read, write (each 0-7).
    Write digit: 4=operator, 6=admin, 7=root. 0/1 = not writable by normal users.
    Also respect readonly/const on the type element.
    """
    if type_elem is not None:
        if type_elem.get("readonly") in ("true", "1") or type_elem.get("const") in ("true", "1"):
            return False
    if not security_level or len(security_level) < 4:
        return True
    write_digit = security_level[-1]
    try:
        return int(write_digit) >= 4
    except ValueError:
        return True


def _parse_type(type_elem: ET.Element | None) -> dict[str, Any]:
    """Extract type kind and allowed values/range from a <type> element."""
    out: dict[str, Any] = {"kind": "string", "options": None, "min": None, "max": None}
    if type_elem is None:
        return out
    for child in type_elem:
        local = _local_tag(child.tag)
        if local == "bool":
            true_val = child.get("true", "yes")
            false_val = child.get("false", "no")
            out["kind"] = "bool"
            out["options"] = [true_val, false_val]
            return out
        if local == "enum":
            out["kind"] = "enum"
            entries = []
            for entry in child:
                if _local_tag(entry.tag) == "entry":
                    val = entry.get("value")
                    if val is not None:
                        entries.append(val)
            if entries:
                out["options"] = entries
            return out
        if local == "int":
            out["kind"] = "int"
            min_val = child.get("min")
            max_val = child.get("max")
            if min_val is not None:
                try:
                    out["min"] = int(min_val)
                except ValueError:
                    pass
            if max_val is not None:
                try:
                    out["max"] = int(max_val)
                except ValueError:
                    pass
            return out
    return out


def parse_listdefinitions_xml(xml_text: str) -> dict[str, dict[str, Any]]:
    """
    Parse Axis listdefinitions XML (listformat=xmlschema) into a flat map.
    Key: full parameter path (e.g. root.Image.I0.Appearance.Resolution).
    Value: dict with keys: value, niceName, writable, kind, options, min, max.
    """
    result: dict[str, dict[str, Any]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result
    # Root can be parameterDefinitions or {ns}parameterDefinitions
    if _local_tag(root.tag) != "parameterDefinitions":
        return result

    def walk(groups_path: list[str], elem: ET.Element) -> None:
        for child in elem:
            local = _local_tag(child.tag)
            if local == "group":
                name = child.get("name")
                if name:
                    walk(groups_path + [name], child)
            elif local == "parameter":
                name = child.get("name")
                if not name:
                    continue
                full_path = ".".join(groups_path + [name])
                value = child.get("value", "")
                security = child.get("securityLevel", "")
                nice = child.get("niceName", name)
                type_elems = [c for c in child if _local_tag(c.tag) == "type"]
                type_elem = type_elems[0] if type_elems else None
                type_info = _parse_type(type_elem)
                result[full_path] = {
                    "value": value,
                    "niceName": nice,
                    "writable": _is_writable(security, type_elem),
                    "kind": type_info["kind"],
                    "options": type_info["options"],
                    "min": type_info["min"],
                    "max": type_info["max"],
                }

    # Axis XML often has root > group name="root" > ...
    walk([], root)
    return result


def format_options_display(meta: dict[str, Any]) -> str:
    """
    Return a short human-readable string of allowed values for display.
    e.g. "(options: 1920x1080, 1280x720)" or "(range: 0-100)" or "".
    """
    if not meta:
        return ""
    options = meta.get("options")
    if options is not None and isinstance(options, list) and len(options) <= 20:
        return f"(options: {', '.join(str(x) for x in options)})"
    min_v = meta.get("min")
    max_v = meta.get("max")
    if min_v is not None and max_v is not None:
        return f"(range: {min_v}-{max_v})"
    if min_v is not None:
        return f"(min: {min_v})"
    if max_v is not None:
        return f"(max: {max_v})"
    return ""
