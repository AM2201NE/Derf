package org.derf.messenger;

import android.accessibilityservice.AccessibilityService;
import android.view.accessibility.AccessibilityEvent;
import java.util.List;

public class DerfAccessibilityService extends AccessibilityService {
    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
        if (event.getEventType() == AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED ||
            event.getEventType() == AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED) {

            List<CharSequence> texts = event.getText();
            if (texts != null) {
                for (CharSequence text : texts) {
                    if (text != null && text.toString().contains("DERF:V1:")) {
                        // Trigger Python callback via Pyjnius
                        PythonServiceManager.onDerfTextDetected(text.toString());
                        break;
                    }
                }
            }
        }
    }

    @Override
    public void onInterrupt() {}
}
