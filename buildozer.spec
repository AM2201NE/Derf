[app]
title = Derf
package.name = derf
package.domain = org.derf.messenger
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,zdict,java
version = 1.0.0

requirements = python3,kivy,cryptography,kyber-py,zstandard,pyjnius,plyer,pillow

orientation = portrait
fullscreen = 0

# API 24+ is required to resolve the preadv/pwritev NDK compilation error
android.minapi = 24
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET, SYSTEM_ALERT_WINDOW, BIND_ACCESSIBILITY_SERVICE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, POST_NOTIFICATIONS
android.add_src = DerfAccessibilityService.java

# IMPORTANT: Auto-accept SDK licenses in GitHub Actions
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0