enum MemoryScope { longTerm, midTerm, all }

enum MemoryTone { primary, secondary, tertiary, danger }

class MemoryItem {
  const MemoryItem({
    required this.id,
    required this.title,
    required this.category,
    required this.dateLabel,
    required this.content,
    required this.scope,
    required this.tone,
  });

  final String id;
  final String title;
  final String category;
  final String dateLabel;
  final String content;
  final MemoryScope scope;
  final MemoryTone tone;
}
