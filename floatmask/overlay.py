import json
from pathlib import Path

from kivy.utils import platform

STATE_FILE = Path.home() / ".floatmask_state.json"


def is_android():
    return platform == "android"


def _load_state():
    defaults = {"x": 520, "y": 420, "w": 200, "h": 120, "color": 0, "alpha": 204}
    try:
        if STATE_FILE.exists():
            defaults.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return defaults


def _save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _android_imports():
    from jnius import autoclass, cast

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Settings = autoclass("android.provider.Settings")
    Intent = autoclass("android.content.Intent")
    Uri = autoclass("android.net.Uri")
    BuildVersion = autoclass("android.os.Build$VERSION")
    Context = autoclass("android.content.Context")
    WindowManagerLayoutParams = autoclass("android.view.WindowManager$LayoutParams")
    Gravity = autoclass("android.view.Gravity")
    View = autoclass("android.view.View")
    MotionEvent = autoclass("android.view.MotionEvent")
    Color = autoclass("android.graphics.Color")
    GradientDrawable = autoclass("android.graphics.drawable.GradientDrawable")
    TextView = autoclass("android.widget.TextView")
    FrameLayout = autoclass("android.widget.FrameLayout")
    FrameLayoutLayoutParams = autoclass("android.widget.FrameLayout$LayoutParams")
    AlertDialog = autoclass("android.app.AlertDialog")
    AlertDialogBuilder = autoclass("android.app.AlertDialog$Builder")

    return {
        "autoclass": autoclass,
        "cast": cast,
        "PythonActivity": PythonActivity,
        "Settings": Settings,
        "Intent": Intent,
        "Uri": Uri,
        "BuildVersion": BuildVersion,
        "Context": Context,
        "LayoutParams": WindowManagerLayoutParams,
        "Gravity": Gravity,
        "View": View,
        "MotionEvent": MotionEvent,
        "Color": Color,
        "GradientDrawable": GradientDrawable,
        "TextView": TextView,
        "FrameLayout": FrameLayout,
        "FrameLayoutLayoutParams": FrameLayoutLayoutParams,
        "AlertDialogBuilder": AlertDialogBuilder,
    }


def open_overlay_settings():
    if not is_android():
        return
    a = _android_imports()
    activity = a["PythonActivity"].mActivity
    package_name = activity.getPackageName()
    uri = a["Uri"].parse("package:" + package_name)
    intent = a["Intent"](a["Settings"].ACTION_MANAGE_OVERLAY_PERMISSION, uri)
    activity.startActivity(intent)


class FloatMaskOverlay:
    # (fill_color_with_alpha, stroke_color)
    COLORS = [
        ("#99333333", "#FF111111"),  # 半透明灰
        ("#CC000000", "#FFFFFFFF"),  # 半透明黑
        ("#FF000000", "#FFFFFFFF"),  # 纯黑不透明
    ]

    def __init__(self):
        self.visible = False
        self.touchable = True
        self.state = _load_state()
        self._android = None
        self._wm = None
        self._view = None
        self._params = None
        self._start = None
        # double-tap detection
        self._last_tap_time = 0
        self._DOUBLE_TAP_MS = 300

    def show(self, touchable=True):
        if not is_android():
            self.visible = True
            return
        self.touchable = touchable
        if self._view is None:
            self._create_view()
            self._wm.addView(self._view, self._params)
        else:
            self._apply_flags()
            self._wm.updateViewLayout(self._view, self._params)
        self.visible = True

    def close(self):
        if is_android() and self._view is not None and self._wm is not None:
            try:
                self._wm.removeView(self._view)
            except Exception:
                pass
        self._view = None
        self._params = None
        self.visible = False
        _save_state(self.state)

    def set_touchable(self, touchable):
        self.touchable = touchable
        if not is_android():
            return
        if self._view is None:
            self.show(touchable=touchable)
            return
        self._apply_flags()
        self._wm.updateViewLayout(self._view, self._params)

    def switch_color(self):
        self.state["color"] = (int(self.state.get("color", 0)) + 1) % len(self.COLORS)
        if is_android() and self._view is not None:
            self._apply_background()
        _save_state(self.state)

    def _show_long_press_menu(self):
        """长按弹出菜单：透明度调节 + 关闭"""
        if not is_android():
            return
        a = self._android
        activity = a["PythonActivity"].mActivity
        overlay = self

        from jnius import PythonJavaClass, java_method

        class AlphaClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            def __init__(self, alpha_value):
                super().__init__()
                self._alpha = alpha_value

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                overlay.state["alpha"] = self._alpha
                _save_state(overlay.state)
                overlay._apply_background()

        class CloseClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                overlay.close()

        JString = a["autoclass"]("java.lang.String")
        builder = a["AlertDialogBuilder"](activity)
        builder.setTitle(JString("FloatMask 菜单"))

        items = ["透明度: 低 (30%)", "透明度: 中 (60%)", "透明度: 高 (80%)", "关闭悬浮框"]
        listeners = [
            AlphaClickListener(77),   # 30%  -> alpha 77/255
            AlphaClickListener(153),  # 60%
            AlphaClickListener(204),  # 80%
            CloseClickListener(),
        ]

        # build items array via Java String[]
        arr = [a["autoclass"]("java.lang.String")(it) for it in items]

        from jnius import PythonJavaClass, java_method

        class ItemClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                listeners[which].onClick(dialog, which)
                dialog.dismiss()

        item_listener = ItemClickListener()
        # Use setItems via CharSequence[]
        CharSequence = a["autoclass"]("java.lang.CharSequence")
        ObjectArray = a["autoclass"]("java.lang.reflect.Array")
        # Simpler: use individual setPositiveButton etc. for 4 options via builder items
        builder.setItems(arr, item_listener)
        dialog = builder.create()
        dialog.getWindow().setType(a["LayoutParams"].TYPE_APPLICATION_OVERLAY
                                   if a["BuildVersion"].SDK_INT >= 26
                                   else a["LayoutParams"].TYPE_PHONE)
        dialog.show()

    def _create_view(self):
        a = _android_imports()
        self._android = a
        activity = a["PythonActivity"].mActivity
        self._wm = activity.getSystemService(a["Context"].WINDOW_SERVICE)

        layout_type = a["LayoutParams"].TYPE_APPLICATION_OVERLAY
        if a["BuildVersion"].SDK_INT < 26:
            layout_type = a["LayoutParams"].TYPE_PHONE

        self._params = a["LayoutParams"](
            int(self.state["w"]),
            int(self.state["h"]),
            layout_type,
            0,
            -3,
        )
        self._params.gravity = a["Gravity"].LEFT | a["Gravity"].TOP
        self._params.x = int(self.state["x"])
        self._params.y = int(self.state["y"])
        self._apply_flags()

        frame = a["FrameLayout"](activity)
        frame.setPadding(4, 4, 4, 4)
        self._apply_background(frame)

        hint = a["TextView"](activity)
        JString = a["autoclass"]("java.lang.String")
        hint.setText(a["cast"]("java.lang.CharSequence", JString("FloatMask")))
        hint.setTextSize(12)
        hint.setTextColor(a["Color"].WHITE)
        hint.setPadding(12, 8, 8, 8)
        frame.addView(hint)

        resize = a["TextView"](activity)
        resize.setText(a["cast"]("java.lang.CharSequence", JString("\u2198")))
        resize.setTextSize(22)
        resize.setTextColor(a["Color"].WHITE)
        resize.setGravity(a["Gravity"].CENTER)
        resize_params = a["FrameLayoutLayoutParams"](64, 64)
        resize_params.gravity = a["Gravity"].RIGHT | a["Gravity"].BOTTOM
        frame.addView(resize, resize_params)

        frame.setOnTouchListener(self._make_touch_listener(False))
        frame.setOnLongClickListener(self._make_long_press_listener())
        resize.setOnTouchListener(self._make_touch_listener(True))
        self._view = frame

    def _make_touch_listener(self, resizing):
        from jnius import PythonJavaClass, java_method
        import time

        overlay = self
        MotionEvent = self._android["MotionEvent"] if self._android else None

        class TouchListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnTouchListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
            def onTouch(self, view, event):
                action = event.getAction()
                now_ms = int(time.time() * 1000)

                if action == MotionEvent.ACTION_DOWN:
                    overlay._start = {
                        "raw_x": int(event.getRawX()),
                        "raw_y": int(event.getRawY()),
                        "x": int(overlay._params.x),
                        "y": int(overlay._params.y),
                        "w": int(overlay._params.width),
                        "h": int(overlay._params.height),
                        "moved": False,
                        "time": now_ms,
                    }
                    return True

                if action == MotionEvent.ACTION_MOVE and overlay._start:
                    dx = int(event.getRawX()) - overlay._start["raw_x"]
                    dy = int(event.getRawY()) - overlay._start["raw_y"]
                    if abs(dx) > 8 or abs(dy) > 8:
                        overlay._start["moved"] = True
                    if overlay._start["moved"]:
                        if resizing:
                            overlay._resize(overlay._start["w"] + dx, overlay._start["h"] + dy)
                        else:
                            overlay._move(overlay._start["x"] + dx, overlay._start["y"] + dy)
                        overlay._wm.updateViewLayout(overlay._view, overlay._params)
                    return True

                if action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    if overlay._start and not overlay._start["moved"] and not resizing:
                        # tap — check double tap
                        elapsed = now_ms - overlay._last_tap_time
                        if 0 < elapsed < overlay._DOUBLE_TAP_MS:
                            # double tap: switch color
                            overlay.switch_color()
                            overlay._last_tap_time = 0
                        else:
                            overlay._last_tap_time = now_ms
                    if overlay._start and overlay._start["moved"]:
                        overlay.state.update({
                            "x": int(overlay._params.x),
                            "y": int(overlay._params.y),
                            "w": int(overlay._params.width),
                            "h": int(overlay._params.height),
                        })
                        _save_state(overlay.state)
                    overlay._start = None
                    return True

                # Long press via GestureDetector not available here;
                # detect manually: ACTION_DOWN held > 600ms without move
                return False

        return TouchListener()

    def _make_long_press_listener(self):
        from jnius import PythonJavaClass, java_method
        overlay = self

        class LongClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnLongClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;)Z")
            def onLongClick(self, view):
                overlay._show_long_press_menu()
                return True

        return LongClickListener()

    def _move(self, x, y):
        display = self._wm.getDefaultDisplay()
        width = display.getWidth()
        height = display.getHeight()
        min_visible_x = max(16, int(self._params.width * 0.2))
        min_visible_y = max(16, int(self._params.height * 0.2))
        self._params.x = max(-int(self._params.width) + min_visible_x, min(x, width - min_visible_x))
        self._params.y = max(-int(self._params.height) + min_visible_y, min(y, height - min_visible_y))

    def _resize(self, width, height):
        display = self._wm.getDefaultDisplay()
        max_w = max(80, int(display.getWidth() * 0.3))
        max_h = max(80, int(display.getHeight() * 0.3))
        self._params.width = max(80, min(int(width), max_w))
        self._params.height = max(80, min(int(height), max_h))

    def _apply_flags(self):
        flags = self._android["LayoutParams"].FLAG_NOT_FOCUSABLE
        if not self.touchable:
            flags |= self._android["LayoutParams"].FLAG_NOT_TOUCHABLE
        self._params.flags = flags

    def _apply_background(self, frame=None):
        if frame is None:
            frame = self._view
        a = self._android
        fill, stroke = self.COLORS[int(self.state.get("color", 0))]
        # Apply alpha from state (override alpha channel in fill color)
        alpha = int(self.state.get("alpha", 204))
        drawable = a["GradientDrawable"]()
        base_color = a["Color"].parseColor(fill)
        # blend alpha into color
        r = (base_color >> 16) & 0xFF
        g = (base_color >> 8) & 0xFF
        b = base_color & 0xFF
        final_color = a["Color"].argb(alpha, r, g, b)
        drawable.setColor(final_color)
        drawable.setStroke(4, a["Color"].parseColor(stroke))
        drawable.setCornerRadius(12)
        frame.setBackground(drawable)
