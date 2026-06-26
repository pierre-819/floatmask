import json
from pathlib import Path

from kivy.utils import platform

STATE_FILE = Path.home() / ".floatmask_state.json"


def is_android():
    return platform == "android"


def _load_state():
    defaults = {"x": -1, "y": -1, "w": 200, "h": 120, "color": 0, "alpha": -1}
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


def _run_on_ui_thread(activity, fn):
    """Execute fn() on the Android main UI thread and block until done."""
    from jnius import PythonJavaClass, java_method
    import threading

    done = threading.Event()
    exc_box = []

    class Run(PythonJavaClass):
        __javainterfaces__ = ["java/lang/Runnable"]
        __javacontext__ = "app"

        @java_method("()V")
        def run(self):
            try:
                fn()
            except Exception as e:
                exc_box.append(e)
            finally:
                done.set()

    activity.runOnUiThread(Run())
    done.wait()
    if exc_box:
        raise exc_box[0]


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
    # Try ACTION_MANAGE_OVERLAY_PERMISSION first
    try:
        intent = a["Intent"](a["Settings"].ACTION_MANAGE_OVERLAY_PERMISSION, uri)
        activity.startActivity(intent)
    except Exception:
        # Fallback: open app settings
        intent = a["Intent"](a["Settings"].ACTION_APPLICATION_DETAILS_SETTINGS, uri)
        activity.startActivity(intent)


def check_overlay_permission():
    """Return True if SYSTEM_ALERT_WINDOW permission is granted."""
    if not is_android():
        return True
    try:
        a = _android_imports()
        activity = a["PythonActivity"].mActivity
        return a["Settings"].canDrawOverlays(activity)
    except Exception:
        return False


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
        self._LONG_PRESS_MS = 600
        # minimize state
        self._minimized = False
        self._restore_size = None  # (w, h) before minimize
        self._hint = None
        self._resize_btn = None
        # independent restore button used while main mask is click-through
        self._restore_view = None
        self._restore_params = None

    def show(self, touchable=True):
        if not is_android():
            self.visible = True
            return
        if not check_overlay_permission():
            raise RuntimeError("未获得悬浮窗权限，请先点击步骤1授权")
        self.touchable = touchable
        if self._view is not None and self._wm is not None:
            try:
                self._apply_flags()
                activity = self._android["PythonActivity"].mActivity
                params, view = self._params, self._view
                _run_on_ui_thread(activity, lambda: self._wm.updateViewLayout(view, params))
                if self.touchable:
                    self._hide_restore_button()
                else:
                    self._show_restore_button()
                self.visible = True
                return
            except Exception:
                self._view = None
                self._params = None
        self._create_view()
        activity = self._android["PythonActivity"].mActivity
        view, params = self._view, self._params
        try:
            _run_on_ui_thread(activity, lambda: self._wm.addView(view, params))
        except Exception as e:
            self._view = None
            self._params = None
            raise RuntimeError(f"addView失败: {e}") from e
        if self.touchable:
            self._hide_restore_button()
        else:
            self._show_restore_button()
        self.visible = True

    def close(self):
        self._hide_restore_button()
        if is_android() and self._view is not None and self._wm is not None:
            try:
                android = self._android
                wm, view = self._wm, self._view
                activity = android["PythonActivity"].mActivity
                _run_on_ui_thread(activity, lambda: wm.removeView(view))
            except Exception:
                pass
        self._view = None
        self._params = None
        self._hint = None
        self._resize_btn = None
        self._minimized = False
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
        activity = self._android["PythonActivity"].mActivity
        wm, view, params = self._wm, self._view, self._params
        _run_on_ui_thread(activity, lambda: wm.updateViewLayout(view, params))
        if self.touchable:
            self._hide_restore_button()
        else:
            self._show_restore_button()

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

        class ColorClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                overlay.switch_color()

        class TouchModeClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                overlay.set_touchable(not overlay.touchable)

        class CloseClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/content/DialogInterface$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/content/DialogInterface;I)V")
            def onClick(self, dialog, which):
                overlay.close()

        JString = a["autoclass"]("java.lang.String")
        builder = a["AlertDialogBuilder"](activity)
        builder.setTitle(JString("FloatMask 菜单"))

        mode_item = "点击穿透" if self.touchable else "恢复编辑模式"
        items = ["切换颜色", mode_item, "透明度: 低 (30%)", "透明度: 中 (60%)", "透明度: 高 (80%)", "关闭悬浮框"]
        listeners = [
            ColorClickListener(),
            TouchModeClickListener(),
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

    def _show_restore_button(self):
        if not is_android() or self._wm is None:
            return
        if self._restore_view is not None:
            return
        a = self._android
        activity = a["PythonActivity"].mActivity
        layout_type = a["LayoutParams"].TYPE_APPLICATION_OVERLAY
        if a["BuildVersion"].SDK_INT < 26:
            layout_type = a["LayoutParams"].TYPE_PHONE

        self._restore_params = a["LayoutParams"](88, 88, layout_type, a["LayoutParams"].FLAG_NOT_FOCUSABLE, -3)
        self._restore_params.gravity = a["Gravity"].LEFT | a["Gravity"].TOP
        display = activity.getWindowManager().getDefaultDisplay()
        self._restore_params.x = max(16, int(display.getWidth()) - 120)
        self._restore_params.y = max(120, int(display.getHeight() * 0.45))

        JString = a["autoclass"]("java.lang.String")
        restore = a["TextView"](activity)
        restore.setText(a["cast"]("java.lang.CharSequence", JString("\u21BA")))  # ↺
        restore.setTextSize(28)
        restore.setTextColor(a["Color"].WHITE)
        restore.setGravity(a["Gravity"].CENTER)
        drawable = a["GradientDrawable"]()
        drawable.setColor(a["Color"].argb(210, 0, 0, 0))
        drawable.setStroke(3, a["Color"].WHITE)
        drawable.setCornerRadius(44)
        restore.setBackground(drawable)
        restore.setOnClickListener(self._make_restore_click_listener())
        restore.setOnLongClickListener(self._make_restore_long_listener())

        self._restore_view = restore
        view, params = self._restore_view, self._restore_params
        _run_on_ui_thread(activity, lambda: self._wm.addView(view, params))

    def _hide_restore_button(self):
        if self._restore_view is None or self._wm is None or self._android is None:
            self._restore_view = None
            self._restore_params = None
            return
        try:
            activity = self._android["PythonActivity"].mActivity
            wm, view = self._wm, self._restore_view
            _run_on_ui_thread(activity, lambda: wm.removeView(view))
        except Exception:
            pass
        self._restore_view = None
        self._restore_params = None

    def _make_restore_click_listener(self):
        from jnius import PythonJavaClass, java_method
        overlay = self

        class RestoreClickListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;)V")
            def onClick(self, view):
                overlay.set_touchable(True)

        return RestoreClickListener()

    def _make_restore_long_listener(self):
        from jnius import PythonJavaClass, java_method
        overlay = self

        class RestoreLongListener(PythonJavaClass):
            __javainterfaces__ = ["android/view/View$OnLongClickListener"]
            __javacontext__ = "app"

            @java_method("(Landroid/view/View;)Z")
            def onLongClick(self, view):
                overlay._show_long_press_menu()
                return True

        return RestoreLongListener()

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

        # 首次启动（x=-1）：计算屏幕中央偏右位置
        display = activity.getWindowManager().getDefaultDisplay()
        screen_w = display.getWidth()
        screen_h = display.getHeight()
        if int(self.state["x"]) < 0:
            self.state["x"] = int(screen_w * 0.6)
        if int(self.state["y"]) < 0:
            self.state["y"] = int(screen_h * 0.4)

        self._params.x = int(self.state["x"])
        self._params.y = int(self.state["y"])
        self._apply_flags()

        frame = a["FrameLayout"](activity)
        frame.setPadding(4, 4, 4, 4)
        self._apply_background(frame)

        JString = a["autoclass"]("java.lang.String")

        hint = a["TextView"](activity)
        hint.setText(a["cast"]("java.lang.CharSequence", JString("FloatMask")))
        hint.setTextSize(12)
        hint.setTextColor(a["Color"].WHITE)
        hint.setPadding(12, 8, 8, 8)
        frame.addView(hint)
        self._hint = hint

        # 缩放按钮（右下角）：拖动缩放，轻点最小化
        resize = a["TextView"](activity)
        resize.setText(a["cast"]("java.lang.CharSequence", JString("\u2198")))
        resize.setTextSize(20)
        resize.setTextColor(a["Color"].WHITE)
        resize.setGravity(a["Gravity"].CENTER)
        resize.setPadding(8, 8, 12, 12)
        resize_params = a["FrameLayoutLayoutParams"](88, 88)
        resize_params.gravity = a["Gravity"].RIGHT | a["Gravity"].BOTTOM
        frame.addView(resize, resize_params)
        self._resize_btn = resize

        frame.setOnTouchListener(self._make_touch_listener(False))
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
                        "long_fired": False,
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
                        try:
                            overlay._wm.updateViewLayout(overlay._view, overlay._params)
                        except Exception:
                            pass
                    else:
                        # 静止超过 LONG_PRESS_MS 触发长按
                        if (not resizing
                            and not overlay._start["long_fired"]
                            and (now_ms - overlay._start["time"]) > overlay._LONG_PRESS_MS):
                            overlay._start["long_fired"] = True
                            overlay._show_long_press_menu()
                    return True

                if action in (MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL):
                    if overlay._start and not overlay._start["moved"]:
                        if overlay._minimized:
                            overlay.toggle_minimize()
                        elif resizing:
                            overlay.toggle_minimize()
                        elif not overlay._start["long_fired"]:
                            held = now_ms - overlay._start["time"]
                            if held > overlay._LONG_PRESS_MS:
                                # 长按抬起也算长按
                                overlay._show_long_press_menu()
                            else:
                                # tap — check double tap
                                elapsed = now_ms - overlay._last_tap_time
                                if 0 < elapsed < overlay._DOUBLE_TAP_MS:
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

                return False

        return TouchListener()

    def toggle_minimize(self):
        if not is_android() or self._view is None:
            return
        a = self._android
        activity = a["PythonActivity"].mActivity
        if not self._minimized:
            # 进入最小化：保存当前尺寸，缩小为 80x80 无边框圆点
            self._restore_size = (int(self._params.width), int(self._params.height))
            self._params.width = 80
            self._params.height = 80
            if self._hint is not None:
                self._hint.setVisibility(self._android["View"].GONE)
            if self._resize_btn is not None:
                self._resize_btn.setVisibility(self._android["View"].GONE)
            self._minimized = True
        else:
            w, h = self._restore_size or (200, 120)
            self._params.width = int(w)
            self._params.height = int(h)
            if self._hint is not None:
                self._hint.setVisibility(self._android["View"].VISIBLE)
            if self._resize_btn is not None:
                self._resize_btn.setVisibility(self._android["View"].VISIBLE)
            self._minimized = False
        self._apply_background()
        wm, view, params = self._wm, self._view, self._params
        _run_on_ui_thread(activity, lambda: wm.updateViewLayout(view, params))

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
        max_w = max(80, int(display.getWidth() * 0.8))
        max_h = max(80, int(display.getHeight() * 0.8))
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
        base_color = a["Color"].parseColor(fill)
        # 如果用户在长按菜单中手动调过透明度（alpha >= 0），用用户值覆盖；
        # 否则尊重 COLORS 颜色中预设的 alpha 通道（保证"纯黑不透明"是真不透明）
        user_alpha = int(self.state.get("alpha", -1))
        if user_alpha >= 0:
            r = (base_color >> 16) & 0xFF
            g = (base_color >> 8) & 0xFF
            b = base_color & 0xFF
            final_color = a["Color"].argb(user_alpha, r, g, b)
        else:
            final_color = base_color
        drawable.setColor(final_color)
        if self._minimized:
            drawable.setCornerRadius(40)
        else:
            drawable.setStroke(4, a["Color"].parseColor(stroke))
            drawable.setCornerRadius(12)
        frame.setBackground(drawable)
