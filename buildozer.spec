[app]
title = Derf
package.name = derf
package.domain = org.derf.messenger
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,zdict,java
version = 1.0.0

# PINNED VERSIONS FOR STABLE ANDROID BUILDS
requirements = python3==3.11.8,kivy,cryptography,kyber-py,zstandard,pyjnius,plyer,pillow==10.4.0

orientation = portrait
fullscreen = 0

android.minapi = 24
android.api = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

android.permissions = INTERNET, SYSTEM_ALERT_WINDOW, BIND_ACCESSIBILITY_SERVICE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, POST_NOTIFICATIONS
android.add_src = DerfAccessibilityService.java
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0