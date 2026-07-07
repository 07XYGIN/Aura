import 'package:aifrd_app/core/mock/aura_mock_data.dart';
import 'package:aifrd_app/features/chat/domain/chat_message.dart';
import 'package:aifrd_app/features/memories/domain/memory_item.dart';
import 'package:flutter/foundation.dart';

enum AuraTab { chat, memories, settings }

enum AuthMode { login, register }

class AuraAppState extends ChangeNotifier {
  AuraAppState()
    : _messages = AuraMockData.chatMessages(),
      _memories = AuraMockData.memories();

  bool _isAuthenticated = false;
  bool _isDarkMode = true;
  bool _rememberMe = true;
  bool _acceptedTerms = false;
  bool _isThinking = false;
  AuthMode _authMode = AuthMode.login;
  AuraTab _currentTab = AuraTab.chat;
  MemoryScope _memoryScope = MemoryScope.longTerm;
  String _languageCode = 'zh-CN';
  String _displayName = '林晓云';
  String _email = 'xiaoyun.lin@example.com';
  String _age = '27';
  String _sex = '0';
  final List<ChatMessage> _messages;
  final List<MemoryItem> _memories;

  bool get isAuthenticated => _isAuthenticated;
  bool get isDarkMode => _isDarkMode;
  bool get rememberMe => _rememberMe;
  bool get acceptedTerms => _acceptedTerms;
  bool get isThinking => _isThinking;
  AuthMode get authMode => _authMode;
  AuraTab get currentTab => _currentTab;
  MemoryScope get memoryScope => _memoryScope;
  String get languageCode => _languageCode;
  String get displayName => _displayName;
  String get email => _email;
  String get age => _age;
  String get sex => _sex;
  List<ChatMessage> get messages => List.unmodifiable(_messages);

  List<MemoryItem> get visibleMemories {
    if (_memoryScope == MemoryScope.all) {
      return List.unmodifiable(_memories);
    }

    return List.unmodifiable(
      _memories.where((memory) => memory.scope == _memoryScope),
    );
  }

  int get totalMemories => visibleMemories.length;

  String get initials {
    final trimmed = _displayName.trim();
    if (trimmed.isEmpty) {
      return 'U';
    }
    return trimmed.substring(0, 1).toUpperCase();
  }

  void setAuthMode(AuthMode mode) {
    if (_authMode == mode) {
      return;
    }
    _authMode = mode;
    notifyListeners();
  }

  void setRememberMe(bool value) {
    _rememberMe = value;
    notifyListeners();
  }

  void setAcceptedTerms(bool value) {
    _acceptedTerms = value;
    notifyListeners();
  }

  void enterApp() {
    _isAuthenticated = true;
    _currentTab = AuraTab.chat;
    notifyListeners();
  }

  void deleteAccountMock() {
    _isAuthenticated = false;
    _authMode = AuthMode.login;
    _currentTab = AuraTab.chat;
    notifyListeners();
  }

  void changeTab(AuraTab tab) {
    if (_currentTab == tab) {
      return;
    }
    _currentTab = tab;
    notifyListeners();
  }

  void setLanguage(String code) {
    _languageCode = code;
    notifyListeners();
  }

  void setDarkMode(bool value) {
    _isDarkMode = value;
    notifyListeners();
  }

  void setMemoryScope(MemoryScope scope) {
    if (_memoryScope == scope) {
      return;
    }
    _memoryScope = scope;
    notifyListeners();
  }

  void updateProfile({
    required String displayName,
    required String email,
    required String age,
    required String sex,
  }) {
    _displayName = displayName.trim().isEmpty
        ? _displayName
        : displayName.trim();
    _email = email.trim();
    _age = age.trim();
    _sex = sex;
    notifyListeners();
  }

  Future<void> sendMessage(String content) async {
    final trimmed = content.trim();
    if (trimmed.isEmpty || _isThinking) {
      return;
    }

    _messages.add(
      ChatMessage(
        id: 'user-${DateTime.now().microsecondsSinceEpoch}',
        sender: ChatSender.user,
        content: trimmed,
        sentAt: DateTime.now(),
      ),
    );
    _isThinking = true;
    notifyListeners();

    await Future<void>.delayed(const Duration(milliseconds: 850));

    _messages.add(
      ChatMessage(
        id: 'aura-${DateTime.now().microsecondsSinceEpoch}',
        sender: ChatSender.aura,
        content: trimmed.contains('记忆') || trimmed.contains('回顾')
            ? '我找到了相关线索。你之前把“数字宁静”描述成一种主动选择边界的方式，我会先把这条记忆放在对话旁边，方便我们继续展开。'
            : '我在。先把你刚才说的重点接住：这件事对你不只是效率问题，也和你想保持的节奏有关。我们可以从最具体的一步开始。',
        sentAt: DateTime.now(),
        memoryQuote: trimmed.contains('记忆') || trimmed.contains('回顾')
            ? const ChatMemoryQuote(
                timeLabel: 'YESTERDAY 22:15',
                content: '数字宁静不是关机，而是在噪音中建立一个受控的静谧岛屿。',
              )
            : null,
      ),
    );
    _isThinking = false;
    notifyListeners();
  }
}
