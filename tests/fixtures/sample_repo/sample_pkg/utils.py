"""Sample utility module with intentional issues for testing."""

import os
import json


# 问题：函数过长、嵌套过深
def process_data(data: list[dict], config: dict, mode: str, verbose: bool, max_retries: int, timeout: float) -> dict:
    """处理数据的主函数——故意写得很复杂"""
    result = {"success": 0, "failed": 0, "errors": []}

    for item in data:
        if mode == "full":
            if config.get("validate", False):
                if verbose:
                    print(f"Validating: {item}")
                try:
                    if item.get("id") is None:
                        raise ValueError("Missing ID")
                    for key, rule in config.get("rules", {}).items():
                        if key in item:
                            value = item[key]
                            if rule == "not_empty" and not value:
                                if verbose:
                                    print(f"Empty value for {key}")
                                result["failed"] += 1
                                result["errors"].append({"item": item["id"], "key": key, "reason": "empty"})
                                continue
                            elif rule == "number" and not isinstance(value, (int, float)):
                                if verbose:
                                    print(f"Non-number value for {key}")
                                result["failed"] += 1
                                result["errors"].append({"item": item["id"], "key": key, "reason": "not_number"})
                                continue
                    result["success"] += 1
                except Exception as e:
                    result["failed"] += 1
                    result["errors"].append({"item": item.get("id"), "reason": str(e)})
            else:
                result["success"] += 1
        elif mode == "simple":
            result["success"] += 1
        else:
            result["failed"] += 1

    return result


# 问题：缺少 docstring
def do_thing(x):
    return x * 2


# 问题：不安全代码
def run_command(cmd):
    os.system(cmd)


# 问题：bare except
def load_config(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {}
