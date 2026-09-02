warning: in the working copy of '.github/workflows/android.yml', LF will be replaced by CRLF the next time Git touches it
[1mdiff --git a/.github/workflows/android.yml b/.github/workflows/android.yml[m
[1mindex 2e52d35..8f6024d 100644[m
[1m--- a/.github/workflows/android.yml[m
[1m+++ b/.github/workflows/android.yml[m
[36m@@ -1,4 +1,4 @@[m
[31m-name: Build Derf Android APK[m
[32m+[m[32m﻿name: Build Derf Android APK[m
 [m
 on:[m
   workflow_dispatch:[m
[36m@@ -32,27 +32,48 @@[m [mjobs:[m
 [m
           SDK="$ANDROID_HOME"[m
 [m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "Preparing Android SDK"[m
[32m+[m[32m          echo "SDK: $SDK"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
           mkdir -p "$SDK/cmdline-tools"[m
 [m
[31m-          curl -L \[m
[31m-            -o /tmp/cmdline-tools.zip \[m
[31m-            "https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip"[m
[32m+[m[32m          python3 - <<'PY'[m
[32m+[m[32m          import urllib.request[m
[32m+[m
[32m+[m[32m          url = "https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip"[m
[32m+[m[32m          output = "/tmp/cmdline-tools.zip"[m
[32m+[m
[32m+[m[32m          print("Downloading Android command-line tools...")[m
[32m+[m[32m          print(url)[m
[32m+[m
[32m+[m[32m          urllib.request.urlretrieve(url, output)[m
[32m+[m
[32m+[m[32m          print("Android command-line tools downloaded successfully.")[m
[32m+[m[32m          PY[m
[32m+[m
[32m+[m[32m          echo "Extracting command-line tools..."[m
 [m
           unzip -q /tmp/cmdline-tools.zip -d "$SDK/cmdline-tools"[m
 [m
           rm -rf "$SDK/cmdline-tools/latest"[m
 [m
[31m-          mv "$SDK/cmdline-tools/cmdline-tools" \[m
[31m-             "$SDK/cmdline-tools/latest"[m
[32m+[m[32m          mv \[m
[32m+[m[32m            "$SDK/cmdline-tools/cmdline-tools" \[m
[32m+[m[32m            "$SDK/cmdline-tools/latest"[m
 [m
[31m-          export PATH="$SDK/cmdline-tools/latest/bin:$SDK/platform-tools:$SDK/tools/bin:$PATH"[m
[32m+[m[32m          export PATH="$SDK/cmdline-tools/latest/bin:$SDK/platform-tools:$PATH"[m
 [m
           echo "$SDK/cmdline-tools/latest/bin" >> "$GITHUB_PATH"[m
           echo "$SDK/platform-tools" >> "$GITHUB_PATH"[m
[31m-          echo "$SDK/tools/bin" >> "$GITHUB_PATH"[m
[32m+[m
[32m+[m[32m          echo "Accepting Android SDK licenses..."[m
 [m
           yes | sdkmanager --licenses >/dev/null || true[m
 [m
[32m+[m[32m          echo "Installing required Android SDK packages..."[m
[32m+[m
           sdkmanager \[m
             "platform-tools" \[m
             "platforms;android-33" \[m
[36m@@ -60,38 +81,85 @@[m [mjobs:[m
             "build-tools;35.0.0" \[m
             "build-tools;37.0.0"[m
 [m
[32m+[m[32m          echo "Creating legacy SDK compatibility path..."[m
[32m+[m
           mkdir -p "$SDK/tools"[m
 [m
           ln -sf \[m
             "$SDK/cmdline-tools/latest/bin" \[m
             "$SDK/tools/bin"[m
 [m
[31m-          echo "SDK preparation complete."[m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "Android SDK preparation complete"[m
[32m+[m[32m          echo "========================================"[m
 [m
       - name: Verify Android SDK[m
         shell: bash[m
         run: |[m
           set -e[m
 [m
[31m-          echo "ANDROID_HOME=$ANDROID_HOME"[m
[32m+[m[32m          SDK="$ANDROID_HOME"[m
[32m+[m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "ANDROID_HOME"[m
[32m+[m[32m          echo "$ANDROID_HOME"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
[32m+[m[32m          echo "Checking sdkmanager..."[m
[32m+[m
[32m+[m[32m          "$SDK/tools/bin/sdkmanager" --version[m
[32m+[m
[32m+[m[32m          echo "Checking Android platforms..."[m
 [m
[31m-          "$ANDROID_HOME/tools/bin/sdkmanager" --version[m
[32m+[m[32m          ls -la "$SDK/platforms"[m
 [m
[31m-          find "$ANDROID_HOME/build-tools" \[m
[32m+[m[32m          echo "Checking Android build-tools..."[m
[32m+[m
[32m+[m[32m          ls -la "$SDK/build-tools"[m
[32m+[m
[32m+[m[32m          echo "Searching for aidl..."[m
[32m+[m
[32m+[m[32m          find "$SDK/build-tools" \[m
             -name aidl \[m
             -type f \[m
             -print[m
 [m
[32m+[m[32m          echo "Checking required aidl files..."[m
[32m+[m
[32m+[m[32m          test -f "$SDK/build-tools/33.0.2/aidl" || \[m
[32m+[m[32m            test -f "$SDK/build-tools/35.0.0/aidl" || \[m
[32m+[m[32m            test -f "$SDK/build-tools/37.0.0/aidl"[m
[32m+[m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "Android SDK verification passed"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
       - name: Build APK[m
         shell: bash[m
         run: |[m
[32m+[m[32m          set -e[m
[32m+[m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "Starting Buildozer Android build"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
           buildozer android debug[m
 [m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "Buildozer finished"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
       - name: Find APK[m
         shell: bash[m
         run: |[m
[31m-          echo "=== APK files ==="[m
[31m-          find bin -type f -name "*.apk" -print[m
[32m+[m[32m          echo "========================================"[m
[32m+[m[32m          echo "APK files"[m
[32m+[m[32m          echo "========================================"[m
[32m+[m
[32m+[m[32m          find bin \[m
[32m+[m[32m            -type f \[m
[32m+[m[32m            -name "*.apk" \[m
[32m+[m[32m            -print[m
 [m
       - name: Upload APK[m
         uses: actions/upload-artifact@v4[m
[1mdiff --git a/buildozer.spec b/buildozer.spec[m
[1mindex 002ffcf..c2b2ed3 100644[m
[1m--- a/buildozer.spec[m
[1m+++ b/buildozer.spec[m
[36m@@ -1,4 +1,4 @@[m
[31m-[app][m
[32m+[m[32m﻿[app][m
 [m
 title = Derf[m
 package.name = derf[m
[36m@@ -18,7 +18,7 @@[m [mfullscreen = 0[m
 android.permissions = INTERNET, SYSTEM_ALERT_WINDOW, BIND_ACCESSIBILITY_SERVICE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE, POST_NOTIFICATIONS[m
 android.api = 33[m
 android.minapi = 23[m
[31m-android.sdk = 33[m
[32m+[m[32m# android.sdk is deprecated[m
 android.ndk = 25b[m
 android.archs = arm64-v8a, armeabi-v7a[m
 [m
