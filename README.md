# FloatMask 智能字幕遮挡工具

这是一个基于 Python 的 Android 课程设计项目原型。

## 技术路线

- Python + Kivy 编写 App 主界面
- pyjnius 调用 Android 原生 API
- WindowManager 创建系统级悬浮窗
- Buildozer 免费打包 APK
- 局域网 HTTP + 二维码实现免费扫码下载

## 主要功能

- 悬浮窗权限跳转
- 半透明字幕遮挡框
- 拖动移动
- 右下角拖拽缩放
- 最小尺寸 80x80
- 最大尺寸屏幕宽高 30%
- 至少 20% 保留在可视区域内
- 遮挡模式点击穿透
- 颜色切换
- 位置和尺寸记忆
- 关闭 App 时移除悬浮窗

## 打包说明

Buildozer 推荐在 Linux 或 WSL 中运行：

```bash
python3 -m pip install --user buildozer cython
buildozer -v android debug
```

生成 APK 后通常位于：

```text
bin/floatmask-0.1.0-arm64-v8a_armeabi-v7a-debug.apk
```

## 免费扫码下载

将生成的 APK 改名为 `FloatMask.apk`，然后在项目目录执行：

```bash
python tools/serve_apk.py FloatMask.apk
```

脚本会启动局域网下载服务并生成二维码图片。手机和电脑连接同一个 Wi-Fi 后扫码即可下载。
