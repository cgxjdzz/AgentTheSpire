"""构建统一 AI 审批动作的提示骨架。"""


def build_action_prompt(requirements: str) -> str:
    """返回包含统一动作结构的 AI 提示文本。"""
    requirements_line = requirements.strip() or "请提供必须满足的输入信息。"
    header = (
        "你正在撰写统一 AI 审批动作的指导。"
        " Output ONLY JSON，后续步骤依赖纯 JSON 格式输出。"
    )
    user_input_block = (
        "User Input Requirements:\n"
        f"- {requirements_line}"
    )
    json_template = (
        "Template JSON structure to fill:\n"
        '{"actions": [\n'
        "  {\n"
        '    "kind": "read_file | write_file | run_command | build_project | deploy_mod",\n'
        '    "title": "简要标题，方便审批人员理解",\n'
        '    "reason": "说明动作所需的业务背景与目标",\n'
        '    "payload": {}\n'
        "  }\n"
        "]}\n"
    )
    return "\n\n".join([header, user_input_block, json_template])
