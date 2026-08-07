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
config = _env_override(config)


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
    """Persist non-secret settings. API keys intentionally remain in memory."""
    try:
        import yaml
        config_path = BACKEND_DIR / "config.yaml"
        persisted = _persistable_config(config)
        with open(config_path, "w") as f:
            yaml.safe_dump(persisted, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        print(f"[config] save error: {e}")


def _persistable_config(source):
    """Return a detached config snapshot with credentials removed."""
    persisted = deepcopy(source)
    persisted.get("ai", {}).pop("api_key", None)
    return persisted


def scrub_persisted_secrets():
    """Remove keys written by older versions while preserving other YAML settings."""
    config_path = BACKEND_DIR / "config.yaml"
    if not config_path.exists():
        return
    try:
        import yaml
        with open(config_path) as source:
            persisted = yaml.safe_load(source) or {}
        ai = persisted.get("ai")
        if isinstance(ai, dict) and "api_key" in ai:
            ai.pop("api_key", None)
            with open(config_path, "w") as target:
                yaml.safe_dump(persisted, target, default_flow_style=False, allow_unicode=True)
    except Exception as exc:
        print(f"[config] could not remove persisted secret: {exc}")


def update_ai_config(api_type=None, api_key=None, api_base_url=None, model=None):
    """Update provider settings; a UI-provided key is session-only."""
    if api_type is not None:
        config["ai"]["api_type"] = api_type
    if api_key is not None:
        config["ai"]["api_key"] = api_key
    if api_base_url is not None:
        config["ai"]["api_base_url"] = api_base_url
    if model is not None:
        config["ai"]["model"] = model
    save_config()


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
