def load_toml_config(config_str: str) -> dict:
    import tomlkit

    def _unwrap(value):
        if hasattr(value, "unwrap"):
            value = value.unwrap()

        if isinstance(value, dict):
            return {k: _unwrap(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_unwrap(v) for v in value]
        return value

    document = tomlkit.loads(config_str)
    return _unwrap(document)


def load_json_config(config_str: str) -> dict:
    import json
    return json.loads(config_str)


def load_yaml_config(config_str: str) -> dict:
    import yaml
    return yaml.safe_load(config_str)


def load_json5_config(config_str: str) -> dict:
    import pyjson5
    return pyjson5.loads(config_str)
