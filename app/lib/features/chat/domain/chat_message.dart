enum ChatSender { aura, user }

class ChatMemoryQuote {
  const ChatMemoryQuote({required this.timeLabel, required this.content});

  final String timeLabel;
  final String content;
}

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.sender,
    required this.content,
    required this.sentAt,
    this.memoryQuote,
  });

  final String id;
  final ChatSender sender;
  final String content;
  final DateTime sentAt;
  final ChatMemoryQuote? memoryQuote;

  bool get isUser => sender == ChatSender.user;
}
