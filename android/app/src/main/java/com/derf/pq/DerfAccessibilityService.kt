package com.derf.pq

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import com.chaquo.python.Python

class DerfAccessibilityService : AccessibilityService() {
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null) return
        if (event.eventType == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED ||
            event.eventType == AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED) {

            val texts = event.text
            if (texts != null) {
                for (text in texts) {
                    if (text != null && text.toString().contains("DERF:V1:")) {
                        try {
                            if (Python.isStarted()) {
                                val module = Python.getInstance().getModule("Derf")
                                module.callAttr("safe_copy", text.toString())
                            }
                        } catch (e: Exception) {
                            e.printStackTrace()
                        }
                        break
                    }
                }
            }
        }
    }

    override fun onInterrupt() {}
}
