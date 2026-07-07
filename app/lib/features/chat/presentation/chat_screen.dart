// 页面说明：
// 聊天页使用 StatefulWidget 保存 TextEditingController 和 ScrollController；消息列表、发送中状态和新增消息由 Provider 中的 AuraAppState 提供。
// Flutter 布局上主要使用 Column 拆分顶部栏、Expanded 消息列表和底部输入区；左右消息气泡通过 Row 的 mainAxisAlignment 区分用户与 Arua。

import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/features/chat/domain/chat_message.dart';
import 'package:aifrd_app/shared/widgets/aura_panel.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  final _scrollController = ScrollController();

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();

    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

    return Column(
      children: [
        const _ChatHeader(),
        Expanded(
          child: ListView(
            controller: _scrollController,
            padding: const EdgeInsets.fromLTRB(18, 28, 18, 22),
            children: [
              const _DateSeparator(),
              const SizedBox(height: 24),
              for (final message in appState.messages) ...[
                _MessageRow(message: message),
                const SizedBox(height: 22),
              ],
              if (appState.isThinking) ...[
                const _ThinkingRow(),
                const SizedBox(height: 22),
              ],
            ],
          ),
        ),
        _Composer(
          controller: _messageController,
          onSend: () => _sendMessage(context),
        ),
      ],
    );
  }

  Future<void> _sendMessage(BuildContext context) async {
    final text = _messageController.text;
    _messageController.clear();
    await context.read<AuraAppState>().sendMessage(text);
    _scrollToBottom();
  }

  void _scrollToBottom() {
    if (!_scrollController.hasClients) {
      return;
    }

    _scrollController.animateTo(
      _scrollController.position.maxScrollExtent,
      duration: const Duration(milliseconds: 260),
      curve: Curves.easeOutCubic,
    );
  }
}

class _ChatHeader extends StatelessWidget {
  const _ChatHeader();

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return SafeArea(
      bottom: false,
      child: Container(
        height: 66,
        padding: const EdgeInsets.symmetric(horizontal: 22),
        decoration: BoxDecoration(
          color: aura.bg.withValues(alpha: 0.78),
          border: Border(bottom: BorderSide(color: aura.border)),
        ),
        child: Row(
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(
                color: aura.secondary,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: aura.secondary.withValues(alpha: 0.42),
                    blurRadius: 14,
                    spreadRadius: 2,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            Text(
              'Arua',
              style: TextStyle(
                color: aura.primary,
                fontSize: 26,
                fontWeight: FontWeight.w900,
              ),
            ),
            const Spacer(),
            IconButton(
              tooltip: '账号',
              onPressed: () => ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('账号详情将在后端接入后同步。'))),
              icon: const Icon(Icons.account_circle_outlined, size: 30),
            ),
          ],
        ),
      ),
    );
  }
}

class _DateSeparator extends StatelessWidget {
  const _DateSeparator();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        'TODAY',
        style: TextStyle(
          color: context.aura.textSoft,
          fontSize: 12,
          fontWeight: FontWeight.w800,
          letterSpacing: 4,
        ),
      ),
    );
  }
}

class _MessageRow extends StatelessWidget {
  const _MessageRow({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final isUser = message.isUser;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: isUser
          ? MainAxisAlignment.end
          : MainAxisAlignment.start,
      children: [
        if (!isUser) ...[const _Avatar(label: 'A'), const SizedBox(width: 12)],
        Flexible(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 540),
            child: Column(
              crossAxisAlignment: isUser
                  ? CrossAxisAlignment.end
                  : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: isUser
                        ? aura.surfaceStrong.withValues(alpha: 0.78)
                        : aura.primarySoft,
                    borderRadius: BorderRadius.only(
                      topLeft: Radius.circular(isUser ? 24 : 6),
                      topRight: Radius.circular(isUser ? 6 : 24),
                      bottomLeft: const Radius.circular(24),
                      bottomRight: const Radius.circular(24),
                    ),
                    border: Border.all(
                      color: isUser
                          ? aura.borderStrong.withValues(alpha: 0.56)
                          : aura.border,
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        message.content,
                        style: TextStyle(
                          color: isUser ? aura.text : aura.text,
                          fontSize: 17,
                          height: 1.62,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (message.memoryQuote != null) ...[
                        const SizedBox(height: 16),
                        _MemoryQuoteCard(quote: message.memoryQuote!),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _formatTime(message.sentAt),
                  style: TextStyle(
                    color: aura.textSoft.withValues(alpha: 0.76),
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ),
        if (isUser) ...[const SizedBox(width: 12), const _Avatar(label: 'JD')],
      ],
    );
  }

  String _formatTime(DateTime time) {
    final hour = time.hour > 12 ? time.hour - 12 : time.hour;
    final period = time.hour >= 12 ? 'PM' : 'AM';
    final minute = time.minute.toString().padLeft(2, '0');
    return '$hour:$minute $period';
  }
}

class _MemoryQuoteCard extends StatelessWidget {
  const _MemoryQuoteCard({required this.quote});

  final ChatMemoryQuote quote;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.black.withValues(
          alpha: Theme.of(context).brightness == Brightness.dark ? 0.18 : 0.05,
        ),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: aura.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.history_edu_rounded, color: aura.secondary, size: 18),
              const SizedBox(width: 8),
              Text(
                quote.timeLabel,
                style: TextStyle(
                  color: aura.secondary,
                  fontSize: 11,
                  fontWeight: FontWeight.w900,
                  letterSpacing: 1.4,
                ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          Text(
            '“${quote.content}”',
            style: TextStyle(
              color: aura.textMuted,
              fontSize: 15,
              height: 1.5,
              fontStyle: FontStyle.italic,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _ThinkingRow extends StatelessWidget {
  const _ThinkingRow();

  @override
  Widget build(BuildContext context) {
    return const Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Avatar(label: 'A'),
        SizedBox(width: 12),
        _ThinkingBubble(),
      ],
    );
  }
}

class _ThinkingBubble extends StatelessWidget {
  const _ThinkingBubble();

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return AuraPanel(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      borderRadius: 22,
      color: aura.primarySoft,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _Dot(delay: 0),
          const SizedBox(width: 6),
          _Dot(delay: 120),
          const SizedBox(width: 6),
          _Dot(delay: 240),
        ],
      ),
    );
  }
}

class _Dot extends StatefulWidget {
  const _Dot({required this.delay});

  final int delay;

  @override
  State<_Dot> createState() => _DotState();
}

class _DotState extends State<_Dot> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    Future<void>.delayed(Duration(milliseconds: widget.delay), () {
      if (mounted) {
        _controller.repeat(reverse: true);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return FadeTransition(
      opacity: Tween<double>(begin: 0.35, end: 1).animate(_controller),
      child: Container(
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          color: aura.secondary,
          shape: BoxShape.circle,
        ),
      ),
    );
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Container(
      width: 42,
      height: 42,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: label == 'A' ? aura.primarySoft : aura.surfaceStrong,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: aura.borderStrong.withValues(alpha: 0.62)),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: label == 'A' ? aura.primary : aura.text,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({required this.controller, required this.onSend});

  final TextEditingController controller;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 8, 18, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            AuraPanel(
              padding: const EdgeInsets.fromLTRB(8, 6, 8, 6),
              borderRadius: 32,
              color: aura.surface.withValues(alpha: 0.88),
              child: Row(
                children: [
                  IconButton(
                    tooltip: '附件',
                    onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('附件上传会在 API 对接阶段接入。')),
                    ),
                    icon: const Icon(Icons.attach_file_rounded),
                  ),
                  Expanded(
                    child: TextField(
                      controller: controller,
                      minLines: 1,
                      maxLines: 4,
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => onSend(),
                      style: TextStyle(color: aura.text, fontSize: 16),
                      decoration: InputDecoration(
                        hintText: '给 Arua 发消息...',
                        border: InputBorder.none,
                        enabledBorder: InputBorder.none,
                        focusedBorder: InputBorder.none,
                        filled: false,
                        isDense: true,
                        contentPadding: const EdgeInsets.symmetric(
                          vertical: 12,
                        ),
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: '语音',
                    onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('语音输入会在能力接入阶段开放。')),
                    ),
                    icon: const Icon(Icons.mic_none_rounded),
                  ),
                  DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: aura.primaryGradient,
                      borderRadius: BorderRadius.circular(18),
                    ),
                    child: IconButton(
                      tooltip: '发送',
                      onPressed: onSend,
                      icon: Icon(Icons.send_rounded, color: aura.onGradient),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Arua 可能会分享不准确的信息，请结合事实判断。',
              style: TextStyle(
                color: aura.textSoft.withValues(alpha: 0.7),
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.1,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
