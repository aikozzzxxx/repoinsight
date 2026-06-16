"""Main module — imports from utils."""

from sample_pkg.utils import process_data, do_thing, run_command, load_config


# 问题：硬编码密钥
API_KEY = "sk-1234567890abcdef1234567890abcdef"
SECRET_TOKEN = "my-secret-token-for-testing"


def main():
    """入口函数"""
    data = [{"id": 1, "name": "test"}]
    config = {"validate": True, "rules": {"name": "not_empty"}}
    return process_data(data, config, "full", True, 3, 30.0)


if __name__ == "__main__":
    result = main()
    print(result)
