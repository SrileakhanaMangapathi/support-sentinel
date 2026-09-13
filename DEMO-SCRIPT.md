# Support Sentinel: two-minute demo

Before recording: open the local app, the existing Notion test ticket, and Slack #new-channel. Keep credentials and OAuth settings closed. Leave OpenAI triage unchecked.

00:00-00:15 — Introduce the problem
Say: "Support automations can report success even when the ticket or notification is wrong. Support Sentinel checks the result and repairs mismatches."

00:15-00:40 — Show the actual live result
Open Recent intakes in the local app and select the live Support Sentinel test. Show the verified checks. Switch to the existing Notion ticket, then its matching Slack notification.
Say: "This test email was read from Gmail, logged in Notion, and announced in Slack. We read the ticket and message back to check that their details match. This prototype currently uses rules for triage; AI classification is planned."

00:40-01:20 — Demonstrate recovery (explicitly simulated)
Return to the local app. Select Demo, click New demo request, and choose Wrong ticket priority -> repair. Run verified intake. Expand the mismatch and repair evidence.
Say: "For a repeatable failure test, these apps are simulated. We deliberately store Low priority instead of High. The verifier catches the mismatch, updates the same ticket, and reads it again before accepting success."

01:20-01:40 — Demonstrate the stopping condition
Click New demo request. Choose Persistent ticket failure -> human review. Run verified intake and show Human review.
Say: "If the repair keeps failing, the workflow stops after two attempts. It does not claim success or send an unverified notification."

01:40-02:00 — Close
Return to the successful repair intake from history.
Say: "The key is the evidence: what we expected, what each app actually stored, and what was repaired. Verified intake is complete; the customer's underlying issue remains open for the support team."

Record using Windows Snipping Tool: press Windows+Shift+R, select the browser area, start recording, perform the walkthrough, stop, and save as Support-Sentinel-demo.mp4. You may record narration if microphone controls are available, or narrate separately.

This script reuses the already-authorized live test. It does not create another live ticket or send another Slack message.
