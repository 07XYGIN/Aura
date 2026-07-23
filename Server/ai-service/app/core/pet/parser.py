"""共同宠物聊天命令的高置信度解析器。"""

from __future__ import annotations

import re
from dataclasses import dataclass

SPECIES_ALIASES = {
    "猫": "cat",
    "小猫": "cat",
    "猫咪": "cat",
    "狗": "dog",
    "小狗": "dog",
    "狗狗": "dog",
    "兔": "rabbit",
    "兔子": "rabbit",
    "小兔子": "rabbit",
}
ADOPT_PATTERN = re.compile(
    r"(?:我们\s*)?(?:领养|养)\s*(?:一只|一个)?\s*"
    r"(?P<species>小兔子|兔子|小猫|猫咪|猫|小狗|狗狗|狗)"
    r"(?:\s*[，,]\s*|\s+)?(?:名字)?叫\s*"
    r"(?P<name>[A-Za-z0-9_\u4e00-\u9fff]{1,32})"
)
RENAME_PATTERN = re.compile(
    r"(?:给|把)?(?:宠物|它|小猫|猫咪|小狗|狗狗|兔子)\s*"
    r"(?:改名|名字改成|改叫)\s*(?:叫|为|成)?\s*"
    r"(?P<name>[A-Za-z0-9_\u4e00-\u9fff]{1,32})"
)
NEGATION_OR_HYPOTHESIS = (
    "不想",
    "不要",
    "别给",
    "别让",
    "先别",
    "暂时不",
    "不需要",
    "不能",
    "如果",
    "假如",
    "要是",
)
ADOPTION_DISCUSSION = ("想养", "想领养", "考虑养", "以后养", "以后领养", "能不能养", "可以养吗")


@dataclass(frozen=True)
class PetChatIntent:
    """从自然语言中解析出的宠物动作及可选身份参数。"""

    action: str
    name: str | None = None
    species: str | None = None


def parse_pet_chat_intent(
    message: str,
    *,
    has_pet: bool,
    pet_name: str | None = None,
) -> PetChatIntent | None:
    """解析领养、状态、改名和六种明确照顾命令。

    Args:
        message: 用户本轮原始文本。
        has_pet: 数据库中是否存在共同宠物。摸摸、睡觉等容易与普通亲密对话
            混淆的词，只有同时包含“宠物/它/猫狗兔”且已有宠物时才会命中。
        pet_name: 数据库中真实的宠物名字；提供后，“摸摸团子”这类直接叫名字
            的动作也能命中，但任意未知名字不会被当作宠物。

    Returns:
        高置信度宠物意图；普通聊天返回 ``None``，继续交给 Aura 主模型。
    """

    text = " ".join(str(message or "").strip().split())
    if not text:
        return None
    if any(pattern in text for pattern in NEGATION_OR_HYPOTHESIS):
        return None
    if any(pattern in text for pattern in ADOPTION_DISCUSSION):
        return PetChatIntent("adopt_prompt")

    adoption = ADOPT_PATTERN.search(text)
    if adoption:
        return PetChatIntent(
            "adopt",
            name=adoption.group("name"),
            species=SPECIES_ALIASES[adoption.group("species")],
        )
    if any(word in text for word in ("领养宠物", "养只猫", "养只狗", "养只兔子")):
        return PetChatIntent("adopt_prompt")

    rename = RENAME_PATTERN.search(text)
    if rename is None and has_pet and pet_name and pet_name in text:
        rename = re.search(
            rf"(?:给|把)?{re.escape(pet_name)}\s*(?:改名|名字改成|改叫)"
            r"\s*(?:叫|为|成)?\s*(?P<name>[A-Za-z0-9_\u4e00-\u9fff]{1,32})",
            text,
        )
    if rename and has_pet:
        return PetChatIntent("rename", name=rename.group("name"))

    pet_marker = any(
        marker in text
        for marker in ("宠物", "小猫", "猫咪", "小狗", "狗狗", "兔子", "小兔", "它")
    ) or bool(pet_name and pet_name in text)
    if not has_pet or not pet_marker:
        return None
    if any(phrase in text for phrase in ("看看宠物", "宠物怎么样", "它怎么样", "看看它", "宠物状态")):
        return PetChatIntent("status")
    action_keywords = (
        ("feed", ("喂", "加餐")),
        ("groom", ("梳毛", "梳一梳", "梳梳")),
        ("bathe", ("洗澡", "洗一洗")),
        ("pet", ("摸摸", "摸一摸", "抱抱")),
        ("sleep", ("睡觉", "哄睡", "休息")),
        ("play", ("陪它玩", "陪宠物玩", "和它玩", "玩玩具", "玩一会")),
    )
    for action, keywords in action_keywords:
        if any(keyword in text for keyword in keywords):
            return PetChatIntent(action)
    return None


def is_pet_chat_candidate(message: str) -> bool:
    """粗筛一条消息是否值得查询宠物状态。

    除明确领养/宠物词外，也保留常见照顾动词，以便查询真实名字后识别“摸摸
    团子”。粗筛只决定是否读一次数据库，最终是否截获仍由带真实名字的严格
    解析器决定。
    """

    text = str(message or "").strip()
    if parse_pet_chat_intent(text, has_pet=True) is not None:
        return True
    return any(
        keyword in text
        for keyword in ("喂", "加餐", "梳毛", "洗澡", "摸摸", "抱抱", "哄睡", "睡觉", "玩一会")
    )
