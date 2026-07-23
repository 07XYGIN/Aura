"""根据已经确定并落库的宠物事实生成安全文案。"""

from __future__ import annotations

from typing import Any

SPECIES_NAMES = {"cat": "小猫", "dog": "小狗", "rabbit": "小兔子"}
ACTION_MESSAGES = {
    "feed": "{name}低头认真吃了一会儿，吃完还舔了舔嘴边。",
    "play": "{name}追着玩具跑了几圈，现在还兴致勃勃地看着你。",
    "groom": "{name}安静地让你梳完了毛，整只看起来都蓬松了一点。",
    "bathe": "洗完以后，{name}甩了甩身上的水，一脸正在重新认识世界的样子。",
    "pet": "{name}往你手边靠了靠，舒舒服服地待着。",
    "sleep": "{name}找了个舒服的位置窝好，很快就安静下来了。",
}


def adoption_narrative(name: str, species: str) -> str:
    """生成领养事件文案，只描述已经创建的宠物身份。"""

    species_name = SPECIES_NAMES.get(species, "小家伙")
    return f"我们把{species_name}{name}接回来了。它先四处看了看，然后在我们旁边安静待了下来。"


def action_narrative(name: str, action: str) -> str:
    """根据确定性动作生成简短文案，不添加数据库中不存在的事件。"""

    template = ACTION_MESSAGES.get(action, "{name}安静地接受了这次照顾。")
    return template.format(name=name)


def rename_narrative(old_name: str, new_name: str) -> str:
    """生成宠物改名事件文案。"""

    return f"从现在开始，它叫{new_name}。我会记住，不再叫它{old_name}了。"


def pet_snapshot_messages(snapshot: dict[str, Any]) -> list[str]:
    """从服务快照提取本轮事件文案或自然状态说明。

    Returns:
        一到两条适合聊天气泡的文本；幂等重放会明确说明动作已经记录，避免
        让用户误以为同一动作执行了两次。
    """

    event = snapshot.get("event") or {}
    if snapshot.get("idempotentReplay"):
        return ["这件事已经记下了，没有重复操作。", event.get("narrative") or snapshot.get("statusText", "")]
    if event.get("narrative"):
        return [str(event["narrative"])]
    status_text = snapshot.get("statusText")
    return [str(status_text or "宠物现在安安静静的。")]
