[app]
title = Derf PQ Messenger
package.name = derfpq
package.domain = com.derf.pq
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,zdict,json,txt
version = 1.0.0

requirements = python3,kivy==2.3.0,cryptography,kyber-py,zstandard,plyer,pillow

orientation = portrait
fullscreen = 0

android.api = 33
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,VIBRATE

[buildozer]
log_level = 2
warn_on_root = 1
