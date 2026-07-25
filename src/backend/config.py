"""
应用配置。优先级：环境变量 > config.yaml > 默认值
"""
import os
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
    }
    for env_var, (section, key) in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            if key == "port":
                val = int(val)
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
