[app]
title = Derf PQ Messenger
package.name = derf
package.domain = org.derf.messenger
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt
version = 1.0.0
requirements = python3,kivy,cryptography,kyber-py,pyjnius

android.permissions = INTERNET,SYSTEM_ALERT_WINDOW,BIND_ACCESSIBILITY_SERVICE
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a

android.add_src = DerfAccessibilityService.java
