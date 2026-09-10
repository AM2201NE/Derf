"""
Derf PQ Messenger Android Accessibility Service Injector.
Automatically injects DerfAccessibilityService into the Briefcase Android Gradle build tree.
Run this script after running `briefcase create android`.
"""
import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GRADLE_APP_DIR = os.path.join(BASE_DIR, "build", "derf", "android", "gradle", "app", "src", "main")

def inject():
    if not os.path.exists(GRADLE_APP_DIR):
        print(f"[!] Android Gradle project directory not found at: {GRADLE_APP_DIR}")
        print("[!] Please run 'briefcase create android' first.")
        sys.exit(1)

    # 1. Copy Java Accessibility Service Source
    java_dest_dir = os.path.join(GRADLE_APP_DIR, "java", "org", "derf", "messenger")
    os.makedirs(java_dest_dir, exist_ok=True)
    java_src = os.path.join(BASE_DIR, "DerfAccessibilityService.java")
    java_dst = os.path.join(java_dest_dir, "DerfAccessibilityService.java")
    if os.path.exists(java_src):
        shutil.copy2(java_src, java_dst)
        print(f"[+] Copied DerfAccessibilityService.java -> {java_dst}")

    # 2. Create XML Accessibility Configuration
    xml_dest_dir = os.path.join(GRADLE_APP_DIR, "res", "xml")
    os.makedirs(xml_dest_dir, exist_ok=True)
    xml_file = os.path.join(xml_dest_dir, "accessibility_service_config.xml")
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:description="@string/accessibility_service_description"
    android:accessibilityEventTypes="typeViewTextChanged|typeViewTextSelectionChanged"
    android:accessibilityFlags="flagDefault"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:notificationTimeout="100"
    android:canRetrieveWindowContent="true" />
"""
    with open(xml_file, "w", encoding="utf-8") as f:
        f.write(xml_content)
    print(f"[+] Created accessibility_service_config.xml -> {xml_file}")

    # 3. Add String Resource
    strings_file = os.path.join(GRADLE_APP_DIR, "res", "values", "strings.xml")
    if os.path.exists(strings_file):
        with open(strings_file, "r", encoding="utf-8") as f:
            s_content = f.read()
        if "accessibility_service_description" not in s_content:
            s_content = s_content.replace(
                "</resources>",
                '    <string name="accessibility_service_description">Derf PQ Messenger Automatic Ciphertext Detection Service</string>\n</resources>'
            )
            with open(strings_file, "w", encoding="utf-8") as f:
                f.write(s_content)
            print("[+] Added accessibility_service_description string resource.")

    # 4. Inject Service Tag into AndroidManifest.xml
    manifest_file = os.path.join(GRADLE_APP_DIR, "AndroidManifest.xml")
    if os.path.exists(manifest_file):
        with open(manifest_file, "r", encoding="utf-8") as f:
            m_content = f.read()

        service_xml = """
        <!-- Derf Post-Quantum Accessibility Service -->
        <service
            android:name="org.derf.messenger.DerfAccessibilityService"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE"
            android:exported="true">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/accessibility_service_config" />
        </service>
"""
        if "org.derf.messenger.DerfAccessibilityService" not in m_content:
            m_content = m_content.replace("</application>", service_xml + "\n    </application>")
            with open(manifest_file, "w", encoding="utf-8") as f:
                f.write(m_content)
            print("[+] Injected DerfAccessibilityService service declaration into AndroidManifest.xml!")

    print("\n[SUCCESS] Android Accessibility Service injected 100% successfully!")

if __name__ == "__main__":
    inject()
