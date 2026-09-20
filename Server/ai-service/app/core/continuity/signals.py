"""Conservative evidence filters shared by relationship state and expression policy."""
from __future__ import annotations

import re


def direct_clauses(message: str) -> list[str]:
    """Only unquoted, non-hypothetical assertions can change persistent state.

    This deliberately prefers a missed event to persisting an uncertain claim.
    It is a fallback filter, not a general natural-language understanding model.
    """
    text = re.sub(r'```[\s\S]*?```|“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"|‘[^’]*’', "", message or "")
    clauses = []
    for sentence in re.split(r"[。！!\n]", text):
        if re.search(r"[？?]|(?:如果|假如|假设|要是|比如|例如|小说|台词|剧本|翻译|举例|转述|引用|开玩笑)", sentence):
            continue
        if re.search(r"(?:他|她|别人|朋友).{0,8}(?:说|问|讲)|(?:你|我)(?:之前|以前|当时|曾经|刚才)?说", sentence):
            continue
        if re.search(r"(?:以前|当时|曾经|那时候|过去).{0,20}(?:喜欢|爱你|在一起|女朋友|恋人)", sentence):
            continue
        clauses.extend(part.strip() for part in re.split(r"[，,；;]", sentence) if part.strip())
    return clauses


def asserted_match(clauses: list[str], patterns: tuple[str, ...]) -> bool:
    for clause in clauses:
        for pattern in patterns:
            for match in re.finditer(pattern, clause):
                prefix = clause[:match.start()]
                if re.search(r"(?:不|没|没有|并非|不是|不会|不再|别|不要).{0,6}$", prefix):
                    continue
                if re.search(r"(?:吗|么|的话|才怪|是假的|不是真的)\s*$", clause[match.end():]):
                    continue
                return True
    return False


def is_task_request(message: str) -> bool:
    text = (message or "").strip()
    return bool(re.search(
        r"(?:帮我|请|能否|能不能|怎么|如何|解释|分析|修复|排查|查一下|写个|写一|修改|计算|翻译).{0,60}"
        r"(?:代码|报错|错误|SQL|接口|数据库|bug|函数|脚本|方案|文档|文章|题|公式|单词|事务|配置|部署)"
        r"|(?:Traceback|UndefinedTable|SELECT\s|Exception|```)|(?:\b500\b).{0,10}(?:查|错)",
        text, re.IGNORECASE,
    ))


def declines_contact(message: str) -> bool:
    return asserted_match(direct_clauses(message), (
        r"(?:别黏我|别烦我|别追问|别问了|别打扰|不要打扰|停一下|先停|我现在不想聊|我要睡了|我先去忙|先走了|晚安)",
    ))
