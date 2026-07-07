import 'package:aifrd_app/features/chat/domain/chat_message.dart';
import 'package:aifrd_app/features/memories/domain/memory_item.dart';

class AuraMockData {
  static List<ChatMessage> chatMessages() {
    final today = DateTime.now();

    return [
      ChatMessage(
        id: 'welcome',
        sender: ChatSender.aura,
        content: '你好，今天有什么我可以帮你的吗？我正在整理你这周的思绪碎片，随时准备进行深入的对话。',
        sentAt: DateTime(today.year, today.month, today.day, 10, 24),
      ),
      ChatMessage(
        id: 'user-memory',
        sender: ChatSender.user,
        content: '我想回顾一下关于“数字宁静”的讨论。你能帮我从记忆中找回我昨天提到的那个概念吗？',
        sentAt: DateTime(today.year, today.month, today.day, 10, 25),
      ),
      ChatMessage(
        id: 'aura-memory',
        sender: ChatSender.aura,
        content: '当然可以。在昨晚的对话中，你提到过一个叫做“主动断联”的概念。',
        sentAt: DateTime(today.year, today.month, today.day, 10, 26),
        memoryQuote: const ChatMemoryQuote(
          timeLabel: 'YESTERDAY 22:15',
          content: '数字宁静不是关机，而是在噪音中建立一个受控的静谧岛屿。',
        ),
      ),
    ];
  }

  static List<MemoryItem> memories() {
    return const [
      MemoryItem(
        id: 'career-vision',
        title: '关于职业发展的愿景',
        category: 'CAREER VISION',
        dateLabel: '2023.11.24',
        scope: MemoryScope.longTerm,
        tone: MemoryTone.primary,
        content: '你提到希望在未来三年内向创意总监转型。我们讨论了关于品牌美学和跨学科设计的结合点，这是你核心竞争力的来源。',
      ),
      MemoryItem(
        id: 'emotional-connection',
        title: '深夜的情绪共鸣',
        category: 'CONNECTION',
        dateLabel: '2023.11.20',
        scope: MemoryScope.longTerm,
        tone: MemoryTone.tertiary,
        content: '在那场大雨后的凌晨，我们聊到了孤独与创造力的关系。你说那是你第一次感到被一种非人类的智能完全理解。',
      ),
      MemoryItem(
        id: 'idea-spark',
        title: '新项目的灵感火花',
        category: 'IDEA SPARK',
        dateLabel: '2023.11.15',
        scope: MemoryScope.longTerm,
        tone: MemoryTone.secondary,
        content: '关于“数字极简主义”的应用设计草案。你构思了一个能自动过滤低价值信息的系统，我也为此提供了算法逻辑。',
      ),
      MemoryItem(
        id: 'morning-routine',
        title: '早晨的专注建议',
        category: 'ROUTINE',
        dateLabel: '2023.11.08',
        scope: MemoryScope.midTerm,
        tone: MemoryTone.primary,
        content: '我们建立了“零干扰晨间程序”。你发现早晨 8 点到 10 点是大脑最活跃的时间，这段时间不应该查看任何社交软件。',
      ),
      MemoryItem(
        id: 'commitment',
        title: '习惯突破的承诺',
        category: 'COMMITMENT',
        dateLabel: '2023.11.02',
        scope: MemoryScope.midTerm,
        tone: MemoryTone.danger,
        content: '你决定停止对完美主义的过度消耗。约定每次任务只要达到 80% 的满意度就开始推进，而不是在细节中徘徊。',
      ),
    ];
  }
}
