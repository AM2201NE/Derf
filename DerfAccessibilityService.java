package org.derf.messenger;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import android.util.Log;

public class DerfAccessibilityService extends AccessibilityService {
    private static final String TAG = "DerfAccessibility";

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        int eventType = event.getEventType();
        if (eventType == AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED ||
            eventType == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED) {
            Log.d(TAG, "Text selection event detected in Derf background layer.");
        }
    }

    @Override
    public void onInterrupt() {
        Log.d(TAG, "DerfAccessibilityService interrupted");
    }
}
