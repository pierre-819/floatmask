[app]
title = FloatMask
package.name = floatmask
package.domain = org.course

source.dir = .
source.include_exts = py,png,jpg,kv,json

version = 0.1.0
requirements = python3,kivy,jnius

orientation = portrait
fullscreen = 0

android.permissions = SYSTEM_ALERT_WINDOW, FOREGROUND_SERVICE, POST_NOTIFICATIONS
android.api = 35
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
p4a.branch = v2024.01.21

# Build with Buildozer on Linux/WSL. Windows can edit and serve APK, but Android packaging is best done in WSL.
# Command: buildozer -v android debug

[buildozer]
log_level = 2
warn_on_root = 0
