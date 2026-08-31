[app]
title = Derf
package.name = derf
package.domain = org.derf
source.dir = .
source.include_patterns = assets/*,images/*.png,*.py,buildozer_spec_additions.txt,Derf.py,derf_bg.py
version = 1.0.0
requirements = python3,kivy,pyjnius,plyer,cryptography,kyber_py,oqs

[buildozer]
log_level = 2

[app:android]
android.debug_artifact = apk
android.release_artifact = apk
fullscreen = 0
android.presplash_color = #000000
android.permissions = INTERNET,ACCESS_NETWORK_STATE,SYSTEM_ALERT_WINDOW,ACCESSIBILITY_SERVICE,WRITE_SECURE_STORAGE,READ_CLIPBOARD,WRITE_CLIPBOARD
android.api = 31
android.minapi = 21
android.sdk = 33
android.private_data = 1
android.build = 1
python.version = 3.12.9
android.ouya.category = GAME
