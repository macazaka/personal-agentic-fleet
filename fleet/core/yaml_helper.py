"""
Pure-Python zero-dependency YAML parser and serializer for Personal Agentic Fleet.
Gracefully leverages PyYAML if installed, otherwise uses a robust, deterministic
internal parser supporting nested dictionaries, lists, inline arrays, comments,
and standard scalar types (strings, booleans, integers, floats, null).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


def parse_yaml_scalar(val_str: str) -> Any:
    """Parses a YAML scalar string into the appropriate Python type."""
    val_str = val_str.strip()
    if not val_str:
        return ""

    # Quoted strings
    if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
        return val_str[1:-1]

    low = val_str.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if low in ("null", "none", "~"):
        return None

    # Inline JSON-style array: e.g. ["monday", "tuesday"]
    if val_str.startswith("[") and val_str.endswith("]"):
        try:
            return json.loads(val_str)
        except Exception:
            items = val_str[1:-1].split(",")
            return [parse_yaml_scalar(x) for x in items if x.strip()]

    # Inline JSON-style object: e.g. {"key": "val"}
    if val_str.startswith("{") and val_str.endswith("}"):
        try:
            return json.loads(val_str)
        except Exception:
            pass

    # Numbers
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def _strip_comments_and_tokenize(text: str) -> List[Tuple[int, str]]:
    """Strips comments while respecting quotes, returning (indent, clean_line) pairs."""
    lines: List[Tuple[int, str]] = []
    for raw in text.splitlines():
        in_quotes = False
        quote_char = ""
        clean_chars = []
        for ch in raw:
            if ch in ('"', "'"):
                if not in_quotes:
                    in_quotes = True
                    quote_char = ch
                elif quote_char == ch:
                    in_quotes = False
            elif ch == "#" and not in_quotes:
                break
            clean_chars.append(ch)
        line = "".join(clean_chars).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        lines.append((indent, line.strip()))
    return lines


def _parse_yaml_lines(lines: List[Tuple[int, str]], idx: int = 0, current_indent: int = 0) -> Tuple[Any, int]:
    """Recursive parser for YAML token lines."""
    if idx >= len(lines):
        return None, idx

    first_indent, first_line = lines[idx]
    if first_indent < current_indent:
        return None, idx

    is_list = first_line.startswith("- ") or first_line == "-"

    if is_list:
        result_list: List[Any] = []
        while idx < len(lines):
            indent, line = lines[idx]
            if indent < current_indent:
                break
            if not (line.startswith("- ") or line == "-"):
                break

            item_content = line[2:].strip() if line.startswith("- ") else ""
            idx += 1

            if not item_content:
                # Value is defined on subsequent indented lines
                child_val, idx = _parse_yaml_lines(lines, idx, indent + 2)
                result_list.append(child_val)
            elif ":" in item_content and not (item_content.startswith("{") or item_content.startswith("[")):
                # Dict item starting on the same line as dash: e.g. - agent: overview
                dict_item: Dict[str, Any] = {}
                k, v = item_content.split(":", 1)
                k = k.strip()
                v = v.strip()
                if v:
                    dict_item[k] = parse_yaml_scalar(v)
                else:
                    dict_item[k], idx = _parse_yaml_lines(lines, idx, indent + 2)

                # Collect sibling keys of this dict at indent + 2 or indent + 4
                while idx < len(lines):
                    next_indent, next_line = lines[idx]
                    if next_indent <= indent:
                        break
                    if next_line.startswith("- ") or next_line == "-":
                        break
                    if ":" in next_line:
                        nk, nv = next_line.split(":", 1)
                        nk = nk.strip()
                        nv = nv.strip()
                        idx += 1
                        if nv:
                            dict_item[nk] = parse_yaml_scalar(nv)
                        else:
                            dict_item[nk], idx = _parse_yaml_lines(lines, idx, next_indent + 2)
                    else:
                        idx += 1
                result_list.append(dict_item)
            else:
                result_list.append(parse_yaml_scalar(item_content))
        return result_list, idx

    else:
        # Mapping block
        result_map: Dict[str, Any] = {}
        while idx < len(lines):
            indent, line = lines[idx]
            if indent < current_indent:
                break
            if indent > current_indent:
                break

            if ":" not in line:
                idx += 1
                continue

            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            idx += 1

            if v:
                result_map[k] = parse_yaml_scalar(v)
            else:
                if idx < len(lines) and lines[idx][0] > indent:
                    child_indent = lines[idx][0]
                    child_val, idx = _parse_yaml_lines(lines, idx, child_indent)
                    result_map[k] = child_val
                else:
                    result_map[k] = {}
        return result_map, idx


def safe_load_yaml(text: str) -> Any:
    """
    Parses YAML text into native Python data structures (dict, list, str, int, float, bool, None).
    Uses PyYAML if available; otherwise uses built-in pure Python fallback parser.
    """
    if not text or not text.strip():
        return {}

    try:
        import yaml
        return yaml.safe_load(text)
    except (ImportError, Exception):
        pass

    lines = _strip_comments_and_tokenize(text)
    if not lines:
        return {}
    parsed, _ = _parse_yaml_lines(lines, 0, 0)
    return parsed if parsed is not None else {}


def load_yaml_file(filepath: Union[str, Path]) -> Any:
    """Loads and parses a YAML file from disk with UTF-8 encoding."""
    p = Path(filepath)
    if not p.is_file():
        return {}
    content = p.read_text(encoding="utf-8")
    return safe_load_yaml(content)


def dump_yaml(data: Any, indent: int = 0) -> str:
    """
    Serializes Python data structures to standard YAML format.
    Uses PyYAML if available; otherwise uses deterministic pure Python serializer.
    """
    try:
        import yaml
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
    except (ImportError, Exception):
        pass

    lines: List[str] = []
    prefix = " " * indent

    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (dict, list)) and v:
                lines.append(f"{prefix}{k}:")
                lines.append(dump_yaml(v, indent + 2))
            elif isinstance(v, list) and not v:
                lines.append(f"{prefix}{k}: []")
            elif isinstance(v, dict) and not v:
                lines.append(f"{prefix}{k}: {{}}")
            elif v is None:
                lines.append(f"{prefix}{k}: null")
            elif isinstance(v, bool):
                lines.append(f"{prefix}{k}: {'true' if v else 'false'}")
            elif isinstance(v, (int, float)):
                lines.append(f"{prefix}{k}: {v}")
            elif isinstance(v, str):
                escaped = v.replace('"', '\\"')
                lines.append(f'{prefix}{k}: "{escaped}"')
            else:
                lines.append(f"{prefix}{k}: {v}")

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                first = True
                for k, v in item.items():
                    if first:
                        if isinstance(v, (dict, list)) and v:
                            lines.append(f"{prefix}- {k}:")
                            lines.append(dump_yaml(v, indent + 4))
                        elif isinstance(v, bool):
                            lines.append(f"{prefix}- {k}: {'true' if v else 'false'}")
                        elif isinstance(v, (int, float)):
                            lines.append(f"{prefix}- {k}: {v}")
                        elif v is None:
                            lines.append(f"{prefix}- {k}: null")
                        elif isinstance(v, str):
                            escaped = v.replace('"', '\\"')
                            lines.append(f'{prefix}- {k}: "{escaped}"')
                        else:
                            lines.append(f"{prefix}- {k}: {v}")
                        first = False
                    else:
                        dict_prefix = " " * (indent + 2)
                        if isinstance(v, (dict, list)) and v:
                            lines.append(f"{dict_prefix}{k}:")
                            lines.append(dump_yaml(v, indent + 4))
                        elif isinstance(v, bool):
                            lines.append(f"{dict_prefix}{k}: {'true' if v else 'false'}")
                        elif isinstance(v, (int, float)):
                            lines.append(f"{dict_prefix}{k}: {v}")
                        elif v is None:
                            lines.append(f"{dict_prefix}{k}: null")
                        elif isinstance(v, str):
                            escaped = v.replace('"', '\\"')
                            lines.append(f'{dict_prefix}{k}: "{escaped}"')
                        else:
                            lines.append(f"{dict_prefix}{k}: {v}")
            else:
                lines.append(f"{prefix}- {item}")

    return "\n".join(lines)


def save_yaml_file(filepath: Union[str, Path], data: Any) -> None:
    """Saves data structure to a YAML file with UTF-8 encoding."""
    p = Path(filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    yaml_text = dump_yaml(data)
    p.write_text(yaml_text, encoding="utf-8")
