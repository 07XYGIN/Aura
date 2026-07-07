// 页面说明：
// 记忆页是一个 StatelessWidget，因为当前页面状态都放在 Provider 的 AuraAppState 中：记忆列表、总数、长期/中期/全部筛选。
// 布局上用 CustomScrollView 承载大标题、筛选控件和卡片列表；卡片复用 AuraPanel，让 Flutter 结构接近 PC 端 Card + token 的写法。

import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/features/memories/domain/memory_item.dart';
import 'package:aifrd_app/shared/widgets/aura_panel.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class MemoriesScreen extends StatelessWidget {
  const MemoriesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();

    return Column(
      children: [
        const _MemoriesHeader(),
        Expanded(
          child: CustomScrollView(
            slivers: [
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(18, 30, 18, 18),
                sliver: SliverList.list(
                  children: [
                    _TitleBlock(total: appState.totalMemories),
                    const SizedBox(height: 22),
                    const _ScopePicker(),
                    const SizedBox(height: 22),
                    for (final memory in appState.visibleMemories) ...[
                      _MemoryCard(memory: memory),
                      const SizedBox(height: 18),
                    ],
                    const SizedBox(height: 18),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _MemoriesHeader extends StatelessWidget {
  const _MemoriesHeader();

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return SafeArea(
      bottom: false,
      child: Container(
        height: 66,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        decoration: BoxDecoration(
          color: aura.bg.withValues(alpha: 0.84),
          border: Border(bottom: BorderSide(color: aura.border)),
        ),
        child: Row(
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: aura.primarySoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(Icons.auto_awesome_rounded, color: aura.primary),
            ),
            const SizedBox(width: 14),
            Text(
              'Arua',
              style: TextStyle(
                color: aura.text,
                fontSize: 25,
                fontWeight: FontWeight.w900,
              ),
            ),
            const Spacer(),
            IconButton(
              tooltip: '搜索记忆',
              onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('记忆搜索会在 API 对接阶段接入。')),
              ),
              icon: const Icon(Icons.search_rounded, size: 28),
            ),
            IconButton(
              tooltip: '更多',
              onPressed: () => ScaffoldMessenger.of(
                context,
              ).showSnackBar(const SnackBar(content: Text('更多记忆操作会在后续开放。'))),
              icon: const Icon(Icons.more_vert_rounded, size: 28),
            ),
          ],
        ),
      ),
    );
  }
}

class _TitleBlock extends StatelessWidget {
  const _TitleBlock({required this.total});

  final int total;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '长期记忆',
          style: TextStyle(
            color: aura.text,
            fontSize: 42,
            height: 1.08,
            fontWeight: FontWeight.w900,
          ),
        ),
        const SizedBox(height: 14),
        Text(
          '这里保留了我们共同成长的重要瞬间。',
          style: TextStyle(
            color: aura.textMuted,
            fontSize: 18,
            height: 1.5,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 12),
        Text(
          '当前筛选 $total 条',
          style: TextStyle(
            color: aura.textSoft,
            fontSize: 12,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.2,
          ),
        ),
      ],
    );
  }
}

class _ScopePicker extends StatelessWidget {
  const _ScopePicker();

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AuraAppState>();
    final aura = context.aura;

    return AuraPanel(
      padding: const EdgeInsets.all(6),
      borderRadius: 22,
      color: aura.surfaceStrong.withValues(alpha: 0.36),
      child: Row(
        children: [
          _ScopeButton(
            label: '长期',
            scope: MemoryScope.longTerm,
            selected: appState.memoryScope == MemoryScope.longTerm,
          ),
          _ScopeButton(
            label: '中期',
            scope: MemoryScope.midTerm,
            selected: appState.memoryScope == MemoryScope.midTerm,
          ),
          _ScopeButton(
            label: '全部',
            scope: MemoryScope.all,
            selected: appState.memoryScope == MemoryScope.all,
          ),
        ],
      ),
    );
  }
}

class _ScopeButton extends StatelessWidget {
  const _ScopeButton({
    required this.label,
    required this.scope,
    required this.selected,
  });

  final String label;
  final MemoryScope scope;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Expanded(
      child: InkWell(
        onTap: () => context.read<AuraAppState>().setMemoryScope(scope),
        borderRadius: BorderRadius.circular(17),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          padding: const EdgeInsets.symmetric(vertical: 11),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? aura.primarySoft : Colors.transparent,
            borderRadius: BorderRadius.circular(17),
          ),
          child: Text(
            label,
            style: TextStyle(
              color: selected ? aura.primary : aura.textMuted,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    );
  }
}

class _MemoryCard extends StatelessWidget {
  const _MemoryCard({required this.memory});

  final MemoryItem memory;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final accent = _accentColor(context, memory.tone);

    return AuraPanel(
      padding: const EdgeInsets.all(20),
      borderRadius: 28,
      color: aura.surfaceMuted,
      withShadow: true,
      child: InkWell(
        onTap: () => ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('已选中记忆：${memory.title}'))),
        borderRadius: BorderRadius.circular(22),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 54,
                  height: 54,
                  decoration: BoxDecoration(
                    color: accent.withValues(alpha: 0.14),
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Icon(_iconFor(memory), color: accent, size: 28),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        memory.title,
                        style: TextStyle(
                          color: aura.text,
                          fontSize: 21,
                          height: 1.2,
                          fontWeight: FontWeight.w900,
                        ),
                      ),
                      const SizedBox(height: 7),
                      Text(
                        memory.category,
                        style: TextStyle(
                          color: accent,
                          fontSize: 12,
                          fontWeight: FontWeight.w900,
                          letterSpacing: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  memory.dateLabel,
                  style: TextStyle(
                    color: aura.textSoft,
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.1,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Padding(
              padding: const EdgeInsets.only(left: 70),
              child: Text(
                memory.content,
                style: TextStyle(
                  color: aura.textMuted,
                  fontSize: 16,
                  height: 1.65,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  IconData _iconFor(MemoryItem memory) {
    return switch (memory.tone) {
      MemoryTone.primary => Icons.auto_awesome_rounded,
      MemoryTone.secondary => Icons.lightbulb_outline_rounded,
      MemoryTone.tertiary => Icons.favorite_border_rounded,
      MemoryTone.danger => Icons.flag_outlined,
    };
  }

  Color _accentColor(BuildContext context, MemoryTone tone) {
    final aura = context.aura;

    return switch (tone) {
      MemoryTone.primary => aura.primary,
      MemoryTone.secondary => aura.secondary,
      MemoryTone.tertiary => aura.tertiary,
      MemoryTone.danger => aura.danger,
    };
  }
}
