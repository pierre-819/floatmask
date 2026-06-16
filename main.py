from kivy.app import App
from kivy.lang import Builder
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

from floatmask.overlay import FloatMaskOverlay, is_android, open_overlay_settings

KV = """
RootView:
    orientation: "vertical"
    padding: dp(18)
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
        font_size: "22sp"
        bold: True
        size_hint_y: None
        height: dp(42)

    Label:
        text: root.status_text
        color: 0.18, 0.22, 0.30, 1
        halign: "left"
        valign: "middle"
        text_size: self.width, None
        size_hint_y: None
        height: dp(92)

    Button:
        text: "1. 开启悬浮窗权限"
        size_hint_y: None
        height: dp(48)
        on_release: root.request_permission()

    Button:
        text: "2. 显示/编辑悬浮框"
        size_hint_y: None
        height: dp(48)
        on_release: root.show_editable_mask()

    Button:
        text: "3. 切换到遮挡模式（点击穿透）"
        size_hint_y: None
        height: dp(48)
        on_release: root.enable_pass_through()

    Button:
        text: "切换颜色"
        size_hint_y: None
        height: dp(48)
        on_release: root.switch_color()

    Button:
        text: "关闭悬浮框"
        size_hint_y: None
        height: dp(48)
        on_release: root.close_mask()

    Widget:
"""


class RootView(BoxLayout):
    mask_visible = BooleanProperty(False)
    status_text = StringProperty(
        "使用步骤：先授权悬浮窗权限，再显示悬浮框。编辑时可拖动和拉伸，遮挡模式会开启点击穿透，适合盖住视频字幕。"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.overlay = FloatMaskOverlay()

    def request_permission(self):
        if not is_android():
            self.status_text = "当前不是 Android 环境。请打包 APK 后在真机上测试悬浮窗权限。"
            return
        open_overlay_settings()
        self.status_text = "已跳转到系统设置。授权后回到 FloatMask，点击显示悬浮框。"

    def show_editable_mask(self):
        try:
            self.overlay.show(touchable=True)
            self.mask_visible = True
            self.status_text = "悬浮框已显示。当前为编辑模式：拖动框体移动，拖动右下角调整大小。"
        except Exception as exc:
            self.status_text = f"显示失败：{exc}。请确认已授予悬浮窗权限。"

    def enable_pass_through(self):
        try:
            self.overlay.set_touchable(False)
            self.status_text = "已进入遮挡模式：悬浮框会盖住字幕，点击该区域会穿透到下方视频 App。"
        except Exception as exc:
            self.status_text = f"切换失败：{exc}"

    def switch_color(self):
        try:
            self.overlay.switch_color()
            self.status_text = "已切换遮挡颜色。"
        except Exception as exc:
            self.status_text = f"切换颜色失败：{exc}"

    def close_mask(self):
        self.overlay.close()
        self.mask_visible = False
        self.status_text = "悬浮框已关闭。"


class FloatMaskApp(App):
    def build(self):
        self.title = "FloatMask"
        return Builder.load_string(KV)

    def on_stop(self):
        if hasattr(self.root, "overlay"):
            self.root.overlay.close()


if __name__ == "__main__":
    FloatMaskApp().run()
