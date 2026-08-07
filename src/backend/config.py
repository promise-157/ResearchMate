"""
应用配置。优先级：环境变量 > config.yaml > 默认值
"""
import os
from copy import deepcopy
from pathlib import Path

# 项目根目录（src/backend -> src -> 项目根）
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
ROOT_DIR = PROJECT_DIR.parent


class ConfigSaveError(RuntimeError):
    """A safe configuration persistence error that never includes secret values."""

# ---- 默认配置 ----
DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
        "reload": False,
    },
    "database": {
        "path": str(PROJECT_DIR / "data" / "researchmate.db"),
    },
    "crawler": {
        "max_papers_per_source": 50,
        "request_interval": 2,
        "timeout": 30,
        "enable_generic_fetch": False,
    },
    "ai": {
        "api_type": "openai",
        "api_key": "",
        "key_storage_mode": "session",
        "api_base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "frontend": {
        "dist_dir": str(PROJECT_DIR / "frontend" / "dist"),
        "dev_server": "http://127.0.0.1:5173",
        "dev_port": 5173,
    },
}


def _load_yaml_config():
    """尝试加载 YAML 配置文件，不存在则返回空。"""
    try:
        import yaml
        config_path = BACKEND_DIR / "config.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _deep_merge(base, override):
    """深度合并两个字典。"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_override(config):
    """用环境变量覆盖配置。"""
    env_map = {
        "RESEARCHMATE_HOST": ("server", "host"),
        "RESEARCHMATE_PORT": ("server", "port"),
        "RESEARCHMATE_DB_PATH": ("database", "path"),
        "RESEARCHMATE_AI_TYPE": ("ai", "api_type"),
        "RESEARCHMATE_AI_KEY": ("ai", "api_key"),
        "RESEARCHMATE_AI_URL": ("ai", "api_base_url"),
        "RESEARCHMATE_AI_MODEL": ("ai", "model"),
        "RESEARCHMATE_ENABLE_GENERIC_FETCH": ("crawler", "enable_generic_fetch"),
    }
    for env_var, (section, key) in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            if key == "port":
                val = int(val)
            elif key == "enable_generic_fetch":
                val = val.strip().lower() in {"1", "true", "yes", "on"}
            config[section][key] = val
    return config


# 构建最终配置
yaml_config = _load_yaml_config()
config = _deep_merge(DEFAULTS, yaml_config)
if config["ai"].get("key_storage_mode") not in {"session", "config"}:
    config["ai"]["key_storage_mode"] = "session"
_persisted_api_key = (
    str(config["ai"].get("api_key") or "")
    if config["ai"]["key_storage_mode"] == "config"
    else ""
)
config["ai"]["api_key"] = _persisted_api_key
config = _env_override(config)
_api_key_source = (
    "environment" if os.environ.get("RESEARCHMATE_AI_KEY") is not None
    else "config" if _persisted_api_key
    else "none"
)


def get(section, key=None):
    """获取配置项。"""
    if key:
        return config.get(section, {}).get(key)
    return config.get(section, {})


def get_db_path():
    """获取数据库路径，确保目录存在。"""
    db_path = Path(get("database", "path"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def save_config():
    """Persist settings, including an API key only after explicit config opt-in."""
    config_path = BACKEND_DIR / "config.yaml"
    temp_path = BACKEND_DIR / "config.yaml.tmp"
    try:
        import yaml
        persisted = _persistable_config(config)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        descriptor = os.open(temp_path, flags, 0o600)
        with os.fdopen(descriptor, "w") as f:
            yaml.safe_dump(persisted, f, default_flow_style=False, allow_unicode=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, config_path)
        os.chmod(config_path, 0o600)
    except Exception as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise ConfigSaveError("配置文件保存失败，请检查 config.yaml 所在目录权限") from exc


def _persistable_config(source):
    """Return a detached snapshot honoring the explicit key storage mode."""
    persisted = deepcopy(source)
    ai = persisted.get("ai", {})
    if ai.get("key_storage_mode") == "config" and _persisted_api_key:
        ai["api_key"] = _persisted_api_key
    else:
        ai.pop("api_key", None)
    return persisted


def scrub_persisted_secrets():
    """Remove legacy plaintext keys unless convenience mode explicitly permits one."""
    config_path = BACKEND_DIR / "config.yaml"
    if not config_path.exists():
        return
    try:
        import yaml
        with open(config_path) as source:
            persisted = yaml.safe_load(source) or {}
        ai = persisted.get("ai")
        if (
            isinstance(ai, dict)
            and "api_key" in ai
            and ai.get("key_storage_mode") != "config"
        ):
            ai.pop("api_key", None)
            descriptor = os.open(config_path, os.O_WRONLY | os.O_TRUNC, 0o600)
            os.chmod(config_path, 0o600)
            with os.fdopen(descriptor, "w") as target:
                yaml.safe_dump(persisted, target, default_flow_style=False, allow_unicode=True)
    except Exception as exc:
        print(f"[config] could not remove persisted secret: {exc}")


def get_ai_key_source():
    return _api_key_source


def get_config_path():
    return str(BACKEND_DIR / "config.yaml")


def update_ai_config(
    api_type=None,
    api_key=None,
    key_storage_mode=None,
    api_base_url=None,
    model=None,
):
    """Update AI settings and honor the user's explicit credential storage choice."""
    global _api_key_source, _persisted_api_key
    previous_config = deepcopy(config)
    previous_persisted_key = _persisted_api_key
    previous_source = _api_key_source
    try:
        if key_storage_mode is not None:
            if key_storage_mode not in {"session", "config"}:
                raise ValueError("Key 保存方式无效")
            if (
                key_storage_mode == "config"
                and config["ai"].get("key_storage_mode") != "config"
                and api_key is None
                and _api_key_source == "session"
            ):
                raise ValueError("切换便利模式时请重新输入 API Key，以确认允许明文保存")
            config["ai"]["key_storage_mode"] = key_storage_mode
            if key_storage_mode == "session":
                _persisted_api_key = ""
        if api_type is not None:
            config["ai"]["api_type"] = api_type
        if api_key is not None:
            if api_key:
                config["ai"]["api_key"] = api_key
                if config["ai"]["key_storage_mode"] == "config":
                    _persisted_api_key = api_key
                    _api_key_source = "config"
                else:
                    _persisted_api_key = ""
                    _api_key_source = "session"
            else:
                _persisted_api_key = ""
                environment_key = os.environ.get("RESEARCHMATE_AI_KEY") or ""
                config["ai"]["api_key"] = environment_key
                _api_key_source = "environment" if environment_key else "none"
        elif key_storage_mode == "session" and _api_key_source == "config":
            # Keep it usable in memory, but remove the plaintext disk copy now.
            _api_key_source = "session" if config["ai"].get("api_key") else "none"
        if api_base_url is not None:
            config["ai"]["api_base_url"] = api_base_url
        if model is not None:
            config["ai"]["model"] = model
        save_config()
    except Exception:
        config.clear()
        config.update(previous_config)
        _persisted_api_key = previous_persisted_key
        _api_key_source = previous_source
        raise


def update_crawler_config(max_papers_per_source=None, request_interval=None, timeout=None):
    """Update bounded collection settings and persist non-secret config."""
    values = {
        "max_papers_per_source": max_papers_per_source,
        "request_interval": request_interval,
        "timeout": timeout,
    }
    for key, value in values.items():
        if value is not None:
            config["crawler"][key] = value
    save_config()
