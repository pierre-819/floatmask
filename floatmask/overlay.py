import json
from pathlib import Path

from kivy.utils import platform

STATE_FILE = Path.home() / ".floatmask_state.json"


def is_android():
    return platform == "android"


def _load_state():
    defaults = {"x": 520, "y": 420, "w": 200, "h": 120, "color": 0}
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
    COLORS = [
        ("#99333333", "#FF111111"),
        ("#CC000000", "#FFFFFFFF"),
        ("#FF000000", "#FFFFFFFF"),
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
        hint.setText("FloatMask")
        hint.setTextSize(12)
        hint.setTextColor(a["Color"].WHITE)
        hint.setPadding(12, 8, 8, 8)
        frame.addView(hint)

        resize = a["TextView"](activity)
        resize.setText("↘")
        resize.setTextSize(22)
        resize.setTextColor(a["Color"].WHITE)
        resize.setGravity(a["Gravity"].CENTER)
        resize_params = a["FrameLayoutLayoutParams"](64, 64)
        resize_params.gravity = a["Gravity"].RIGHT | a["Gravity"].BOTTOM
        frame.addView(resize, resize_params)

        frame.setOnTouchListener(self._make_touch_listener(False))
        resize.setOnTouchListener(self._make_touch_listener(True))
        self._view = frame

    def _make_touch_listener(self, resizing):
        from jnius import PythonJavaClass, java_method

        overlay = self
        MotionEvent = self._android["MotionEvent"] if self._android else None

        class TouchListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnTouchListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;Landroid/view/MotionEvent;)Z")
            def onTouch(self, view, event):
                action = event.getAction()
                if action == MotionEvent.ACTION_DOWN:
                    overlay._start = {
                        "raw_x": int(event.getRawX()),
                        "raw_y": int(event.getRawY()),
                        "x": int(overlay._params.x),
                        "y": int(overlay._params.y),
                        "w": int(overlay._params.width),
                        "h": int(overlay._params.height),
                    }
                    return True
                if action == MotionEvent.ACTION_MOVE and overlay._start:
                    dx = int(event.getRawX()) - overlay._start["raw_x"]
                    dy = int(event.getRawY()) - overlay._start["raw_y"]
                    if resizing:
                        overlay._resize(overlay._start["w"] + dx, overlay._start["h"] + dy)
                    else:
                        overlay._move(overlay._start["x"] + dx, overlay._start["y"] + dy)
                    overlay._wm.updateViewLayout(overlay._view, overlay._params)
                    return True
                if action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    overlay._start = None
                    overlay.state.update({
                        "x": int(overlay._params.x),
                        "y": int(overlay._params.y),
                        "w": int(overlay._params.width),
                        "h": int(overlay._params.height),
                    })
                    _save_state(overlay.state)
                    return True
                return False

        return TouchListener()

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
        drawable = a["GradientDrawable"]()
        drawable.setColor(a["Color"].parseColor(fill))
        drawable.setStroke(4, a["Color"].parseColor(stroke))
        frame.setBackground(drawable)
