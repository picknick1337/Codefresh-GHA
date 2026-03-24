from __future__ import annotations

from typing import Any

import yaml


class _BlockStyleDumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper: yaml.SafeDumper, value: str) -> yaml.nodes.ScalarNode:
    if "\n" in value:
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_BlockStyleDumper.add_representer(str, _str_presenter)


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.dump(
        data,
        Dumper=_BlockStyleDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
