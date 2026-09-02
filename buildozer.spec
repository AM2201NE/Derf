[app]
title = Derf
package.name = derf
package.domain = org.derf.messenger
source.dir = .
source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,zdict,java
version = 1.0.0

# Requirements for your app
requirements = python3,kivy,cryptography,kyber-py,zstandard,pyjnius,plyer,pillow

orientation = portrait
fullscreen = 0

# Android specific settings
android.permissions = INTERNET, SYSTEM_ALERT_WINDOW, BIND_ACCESSIBILITY_SERVICE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, POST_NOTIFICATIONS
android.api = 33
android.minapi = 23
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

# Add your custom Java service
android.add_src = DerfAccessibilityService.java

[buildozer]
log_level = 2
warn_on_root = 0