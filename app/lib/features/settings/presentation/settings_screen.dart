// 页面说明：
// 设置页使用 StatefulWidget 保存资料表单的 TextEditingController，保存时再写回 Provider；语言、深色模式、注销账号直接调用 AuraAppState。
// 布局上用 SingleChildScrollView + 多个 AuraPanel 组合成 PC 端设置页的移动版，避免把所有设置堆在一个大组件里。

import 'package:aifrd_app/core/theme/aura_theme.dart';
import 'package:aifrd_app/features/app/application/aura_app_state.dart';
import 'package:aifrd_app/shared/widgets/aura_panel.dart';
import 'package:aifrd_app/shared/widgets/aura_primary_button.dart';
import 'package:aifrd_app/shared/widgets/aura_section_label.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _nameController;
  late final TextEditingController _emailController;
  late final TextEditingController _ageController;
  String _sex = '0';

  @override
  void initState() {
    super.initState();
    final appState = context.read<AuraAppState>();
    _nameController = TextEditingController(text: appState.displayName);
    _emailController = TextEditingController(text: appState.email);
    _ageController = TextEditingController(text: appState.age);
    _sex = appState.sex;
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _ageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;
    final appState = context.watch<AuraAppState>();

    return Column(
      children: [
        const _SettingsHeader(),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(18, 24, 18, 28),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const AuraSectionLabel('用户资料'),
                AuraPanel(
                  padding: const EdgeInsets.all(20),
                  borderRadius: 28,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Row(
                        children: [
                          Container(
                            width: 62,
                            height: 62,
                            alignment: Alignment.center,
                            decoration: BoxDecoration(
                              gradient: aura.primaryGradient,
                              borderRadius: BorderRadius.circular(22),
                            ),
                            child: Text(
                              appState.initials,
                              style: TextStyle(
                                color: aura.onGradient,
                                fontSize: 24,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  appState.displayName,
                                  style: TextStyle(
                                    color: aura.text,
                                    fontSize: 24,
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                                const SizedBox(height: 5),
                                Text(
                                  appState.email,
                                  overflow: TextOverflow.ellipsis,
                                  style: TextStyle(
                                    color: aura.textMuted,
                                    fontSize: 15,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 22),
                      _ProfileField(
                        controller: _nameController,
                        label: '显示名称',
                        icon: Icons.person_outline_rounded,
                      ),
                      const SizedBox(height: 14),
                      _ProfileField(
                        controller: _emailController,
                        label: '邮箱地址',
                        icon: Icons.mail_outline_rounded,
                        keyboardType: TextInputType.emailAddress,
                      ),
                      const SizedBox(height: 14),
                      Row(
                        children: [
                          Expanded(
                            child: _ProfileField(
                              controller: _ageController,
                              label: '年龄',
                              icon: Icons.cake_outlined,
                              keyboardType: TextInputType.number,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: _SexSegment(
                              value: _sex,
                              onChanged: (value) =>
                                  setState(() => _sex = value),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      AuraPrimaryButton(
                        label: '保存资料',
                        icon: Icons.check_rounded,
                        onPressed: _saveProfile,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                const AuraSectionLabel('语言'),
                AuraPanel(
                  padding: const EdgeInsets.all(18),
                  borderRadius: 26,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.language_rounded, color: aura.secondary),
                          const SizedBox(width: 12),
                          Text(
                            '界面语言',
                            style: TextStyle(
                              color: aura.text,
                              fontSize: 20,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _LanguageSegment(selected: appState.languageCode),
                      const SizedBox(height: 12),
                      Text(
                        '切换后会立即应用到当前移动端界面。',
                        style: TextStyle(
                          color: aura.textMuted,
                          height: 1.5,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                const AuraSectionLabel('外观'),
                AuraPanel(
                  padding: const EdgeInsets.all(18),
                  borderRadius: 26,
                  child: Row(
                    children: [
                      Icon(
                        Icons.dark_mode_outlined,
                        color: aura.secondary,
                        size: 28,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '深色模式',
                              style: TextStyle(
                                color: aura.text,
                                fontSize: 20,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Text(
                              '参考 PC 端 Aura 主题切换。',
                              style: TextStyle(
                                color: aura.textMuted,
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Switch(
                        value: appState.isDarkMode,
                        activeThumbColor: aura.onGradient,
                        activeTrackColor: aura.primary,
                        inactiveThumbColor: aura.textSoft,
                        inactiveTrackColor: aura.surfaceStrong,
                        onChanged: context.read<AuraAppState>().setDarkMode,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                const AuraSectionLabel('安全与账号'),
                AuraPanel(
                  padding: const EdgeInsets.all(20),
                  borderRadius: 28,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.shield_outlined, color: aura.danger),
                          const SizedBox(width: 12),
                          Text(
                            '危险操作',
                            style: TextStyle(
                              color: aura.text,
                              fontSize: 21,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(
                        '注销账号需要后端权限、导出和审计流程完成后再开放。当前为前端交互占位。',
                        style: TextStyle(
                          color: aura.textMuted,
                          height: 1.55,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 18),
                      SizedBox(
                        width: double.infinity,
                        child: AuraPrimaryButton(
                          label: '注销账号',
                          icon: Icons.delete_forever_outlined,
                          danger: true,
                          onPressed: _confirmDeleteAccount,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 36),
                Text(
                  'Arua Version 2.4.0 (2024)\nMADE WITH LOVE IN SHANGHAI',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: aura.textSoft.withValues(alpha: 0.66),
                    height: 1.8,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.8,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  void _saveProfile() {
    context.read<AuraAppState>().updateProfile(
      displayName: _nameController.text,
      email: _emailController.text,
      age: _ageController.text,
      sex: _sex,
    );
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('资料已保存到本地 mock 状态。')));
  }

  Future<void> _confirmDeleteAccount() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) {
        final aura = context.aura;

        return AlertDialog(
          backgroundColor: aura.surfaceSolid,
          surfaceTintColor: Colors.transparent,
          title: Text('确认注销账号？', style: TextStyle(color: aura.text)),
          content: Text(
            '当前不会调用真实后端，只会回到登录页用于演示流程。',
            style: TextStyle(color: aura.textMuted),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(false),
              child: const Text('取消'),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(true),
              child: Text('注销账号', style: TextStyle(color: aura.danger)),
            ),
          ],
        );
      },
    );

    if (confirmed == true && mounted) {
      context.read<AuraAppState>().deleteAccountMock();
    }
  }
}

class _SettingsHeader extends StatelessWidget {
  const _SettingsHeader();

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
            Icon(Icons.auto_awesome_rounded, color: aura.primary, size: 28),
            const SizedBox(width: 12),
            Text(
              '设置',
              style: TextStyle(
                color: aura.text,
                fontSize: 25,
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

class _ProfileField extends StatelessWidget {
  const _ProfileField({
    required this.controller,
    required this.label,
    required this.icon,
    this.keyboardType,
  });

  final TextEditingController controller;
  final String label;
  final IconData icon;
  final TextInputType? keyboardType;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      style: TextStyle(color: context.aura.text, fontWeight: FontWeight.w700),
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, color: context.aura.primary, size: 20),
      ),
    );
  }
}

class _SexSegment extends StatelessWidget {
  const _SexSegment({required this.value, required this.onChanged});

  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Container(
      height: 58,
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: aura.surfaceStrong.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: aura.border),
      ),
      child: Row(
        children: [
          _SmallSegmentButton(
            label: '男',
            selected: value == '1',
            onTap: () => onChanged('1'),
          ),
          _SmallSegmentButton(
            label: '女',
            selected: value == '0',
            onTap: () => onChanged('0'),
          ),
        ],
      ),
    );
  }
}

class _LanguageSegment extends StatelessWidget {
  const _LanguageSegment({required this.selected});

  final String selected;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Container(
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: aura.surfaceStrong.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: aura.border),
      ),
      child: Row(
        children: [
          _SmallSegmentButton(
            label: '中文',
            selected: selected == 'zh-CN',
            onTap: () => context.read<AuraAppState>().setLanguage('zh-CN'),
          ),
          _SmallSegmentButton(
            label: 'English',
            selected: selected == 'en-US',
            onTap: () => context.read<AuraAppState>().setLanguage('en-US'),
          ),
          _SmallSegmentButton(
            label: '日本語',
            selected: selected == 'ja-JP',
            onTap: () => context.read<AuraAppState>().setLanguage('ja-JP'),
          ),
        ],
      ),
    );
  }
}

class _SmallSegmentButton extends StatelessWidget {
  const _SmallSegmentButton({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final aura = context.aura;

    return Expanded(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 160),
          alignment: Alignment.center,
          padding: const EdgeInsets.symmetric(vertical: 11),
          decoration: BoxDecoration(
            color: selected ? aura.primary : Colors.transparent,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(
            label,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: selected ? aura.onGradient : aura.textMuted,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ),
    );
  }
}
