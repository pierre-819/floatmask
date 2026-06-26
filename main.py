from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.text import LabelBase
import os

from floatmask.overlay import (
    FloatMaskOverlay,
    is_android,
    open_overlay_settings,
    check_overlay_permission,
)

# 注册中文字体：Kivy 默认字体不支持中文，打包时会把 simSun.ttc 一起放进 APK。
_font_path = os.path.join(os.path.dirname(__file__), "simSun.ttc")
if os.path.exists(_font_path):
    LabelBase.register(name="SimSun", fn_regular=_font_path)
    _FONT = "SimSun"
else:
    _FONT = "Roboto"

# KV 是 Kivy 的界面描述语言，这里直接用字符串定义主页面布局。
KV = f"""
RootView:
    orientation: "vertical"
    padding: dp(18), dp(48), dp(18), dp(18)
    spacing: dp(14)

    canvas.before:
        Color:
            rgba: 0.96, 0.97, 0.98, 1
        Rectangle:
            pos: self.pos
            size: self.size

    Label:
        text: "FloatMask 智能字幕遮挡工具"
        color: 0.08, 0.10, 0.14, 1
        font_name: "{_FONT}"
        font_size: "22sp"
        bold: True
        size_hint_y: None
        height: dp(42)

    Label:
        text: root.status_text
        color: 0.18, 0.22, 0.30, 1
        font_name: "{_FONT}"
        halign: "left"
        valign: "middle"
        text_size: self.width, None
        size_hint_y: None
        height: dp(92)

    Button:
        text: "1. 开启悬浮窗权限"
        font_name: "{_FONT}"
        size_hint_y: None
        height: dp(48)
        on_release: root.request_permission()

    Button:
        text: "2. 显示/编辑悬浮框"
        font_name: "{_FONT}"
        size_hint_y: None
        height: dp(48)
        on_release: root.show_editable_mask()

    Button:
        text: "3. 切换到遮挡模式（点击穿透）"
        font_name: "{_FONT}"
        size_hint_y: None
        height: dp(48)
        on_release: root.enable_pass_through()

    Button:
        text: "切换颜色（或双击悬浮框）"
        font_name: "{_FONT}"
        size_hint_y: None
        height: dp(48)
        on_release: root.switch_color()

    Button:
        text: "关闭悬浮框"
        font_name: "{_FONT}"
        size_hint_y: None
        height: dp(48)
        on_release: root.close_mask()

    Widget:
"""


class RootView(BoxLayout):
    """主页面控制层。

    Kivy 页面只负责按钮、状态提示和权限弹窗；真正的 Android 悬浮窗
    操作全部交给 FloatMaskOverlay，避免 UI 页面和系统窗口逻辑混在一起。
    """
    mask_visible = BooleanProperty(False)
    status_text = StringProperty(
        "使用步骤：先授权悬浮窗权限，再显示悬浮框。编辑时可拖动和拉伸，遮挡模式开启点击穿透。双击悬浮框切换颜色，长按弹出菜单。"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # FloatMaskOverlay 封装 Android WindowManager，主界面通过它控制悬浮窗。
        self.overlay = FloatMaskOverlay()
        # 启动后稍延迟检测权限，避免界面尚未渲染就弹窗。
        Clock.schedule_once(lambda dt: self._check_permission_on_start(), 0.5)

    def _check_permission_on_start(self):
        # 只在 Android 真机上检测；桌面调试时直接跳过，方便本地运行界面。
        if not is_android():
            return
        if check_overlay_permission():
            # 已授权时不打扰用户，避免每次启动都弹窗。
            return
        self._show_permission_dialog()

    def _show_permission_dialog(self):
        # 自定义权限说明弹窗：用户点“允许”后再跳转系统悬浮窗设置页。
        content = BoxLayout(orientation="vertical", spacing=12, padding=16)
        msg = Label(
            text="FloatMask 想要获取您的悬浮窗权限\n用于在视频 App 上方显示遮挡框",
            font_name=_FONT,
            halign="center",
            valign="middle",
        )
        msg.bind(size=lambda s, v: setattr(s, "text_size", v))
        content.add_widget(msg)

        btn_row = BoxLayout(orientation="horizontal", spacing=12, size_hint_y=None, height="48dp")
        btn_cancel = Button(text="取消", font_name=_FONT)
        btn_ok = Button(text="允许", font_name=_FONT)
        btn_row.add_widget(btn_cancel)
        btn_row.add_widget(btn_ok)
        content.add_widget(btn_row)

        popup = Popup(
            title="权限申请",
            title_font=_FONT,
            content=content,
            size_hint=(0.8, 0.4),
            auto_dismiss=False,
        )
        btn_cancel.bind(on_release=lambda *_: popup.dismiss())

        def _allow(*_):
            popup.dismiss()
            open_overlay_settings()
            self.status_text = "已跳转到系统设置。授权后回到 FloatMask，点击显示悬浮框。"
        btn_ok.bind(on_release=_allow)
        popup.open()

    def request_permission(self):
        # 手动权限入口：如果已经授权，只提示状态，不重复打开设置页。
        if not is_android():
            self.status_text = "当前不是 Android 环境。请打包 APK 后在真机上测试悬浮窗权限。"
            return
        if check_overlay_permission():
            self.status_text = "悬浮窗权限已开启，可直接显示悬浮框。"
            return
        open_overlay_settings()
        self.status_text = "已跳转到系统设置。授权后回到 FloatMask，点击显示悬浮框。"

    def show_editable_mask(self):
        # 编辑模式下悬浮框可接收触摸，用于拖动、缩放、双击和长按菜单。
        try:
            self.overlay.show(touchable=True)
            self.mask_visible = True
            self.status_text = "悬浮框已显示。当前为编辑模式：拖动框体移动，拖动右下角调整大小。"
        except Exception as exc:
            self.status_text = f"显示失败：{exc}。请确认已授予悬浮窗权限。"

    def enable_pass_through(self):
        # 遮挡模式会让主悬浮窗点击穿透，overlay 内部会额外显示 ↺ 恢复按钮。
        try:
            self.overlay.set_touchable(False)
            self.status_text = "已进入遮挡模式：悬浮框会盖住字幕，点击该区域会穿透到下方视频 App。"
        except Exception as exc:
            self.status_text = f"切换失败：{exc}"

    def switch_color(self):
        # 没有悬浮窗权限时不允许切换，避免用户误以为已经改变了实际遮挡框。
        if is_android() and not check_overlay_permission():
            self.status_text = "切换失败：请先点击步骤一获取悬浮窗权限。"
            return
        try:
            self.overlay.switch_color()
            self.status_text = "已切换遮挡颜色。"
        except Exception as exc:
            self.status_text = f"切换颜色失败：{exc}"

    def close_mask(self):
        # 关闭主悬浮窗时，overlay 会同时清理穿透恢复按钮和保存状态。
        self.overlay.close()
        self.mask_visible = False
        self.status_text = "悬浮框已关闭。"


class FloatMaskApp(App):
    """Kivy 应用入口。"""

    def build(self):
        self.title = "FloatMask"
        return Builder.load_string(KV)

    def on_stop(self):
        # App 退出时主动移除悬浮窗，避免系统里残留一个不可控的窗口。
        if hasattr(self.root, "overlay"):
            self.root.overlay.close()


if __name__ == "__main__":
    FloatMaskApp().run()
