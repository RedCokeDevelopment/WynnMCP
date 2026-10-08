"""Regenerate the tool catalog from the official OpenAPI specification."""

import argparse
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = "https://docs.wynncraft.com/openapi.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, help="Use a downloaded OpenAPI JSON file")
    args = parser.parse_args()
    if args.spec:
        spec = json.loads(args.spec.read_text(encoding="utf-8-sig"))
    else:
        with urlopen(Request(URL, headers={"User-Agent": "WynnMCP/0.1.0"}), timeout=30) as response:
            spec = json.load(response)

    def expand(value):
        if isinstance(value, list):
            return [expand(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            referenced = spec
            for part in value["$ref"][2:].split("/"):
                referenced = referenced[part]
            return expand({**referenced, **{k: v for k, v in value.items() if k != "$ref"}})
        return {k: expand(v) for k, v in value.items() if k != "title"}

    catalog = {}
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method not in ("get", "post") or path == "/oauth/token":
                continue
            properties, required, parameters = {}, [], []
            for param in op.get("parameters", []):
                name = param["name"]
                flag = "Presence-based flag" in param.get("description", "")
                schema = {"type": "boolean", "default": False} if flag else expand(param["schema"])
                if param.get("description"):
                    schema["description"] = param["description"]
                if flag:
                    schema["description"] += " Set true to include the flag; false omits it."
                properties[name] = schema
                if param.get("required"):
                    required.append(name)
                parameters.append({"name": name, "in": param["in"], "flag": flag})
            if "requestBody" in op:
                properties["filters"] = expand(
                    op["requestBody"]["content"]["application/json"]["schema"]
                )
                properties["filters"]["additionalProperties"] = False
                properties["filters"]["description"] = (
                    "Search filters; omit or use {} for no filters."
                )
            name = re.sub(r"(?<!^)(?=[A-Z])", "_", op["operationId"].split("_", 1)[1]).lower()
            description = op["summary"] + ". "
            raw = op.get("description", "")
            raw = re.sub(r"<[^>]+>", "", raw)
            description += re.sub(r"\s+", " ", raw).strip()
            catalog[name] = {
                "method": method.upper(),
                "path": path,
                "parameters": parameters,
                "description": description,
                "schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                    "additionalProperties": False,
                },
            }
    dest = ROOT / "src/wynnmcp/endpoints.json"
    dest.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {len(catalog)} tools from {URL}")


if __name__ == "__main__":
    main()
