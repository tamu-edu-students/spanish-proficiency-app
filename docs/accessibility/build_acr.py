# Builds the Avanza Español ACR (VPAT 2.5Rev WCAG layout) as HTML.
# Export: PDF via headless Chromium, DOCX via macOS `textutil`.
from html import escape

S, PS, NA, NE = 'Supports', 'Partially Supports', 'Not Applicable', 'Not Evaluated'

LEVEL_A = [
 ('1.1.1 Non-text Content', 'A 2.0, 2.1, 2.2', S, 'Texas A&M logos have text alternatives. Icon-only controls (send message, microphone, accent-character buttons) have accessible names. Decorative emoji and animations are hidden from assistive technology.'),
 ('1.2.1 Audio-only and Video-only (Prerecorded)', 'A 2.0, 2.1, 2.2', S, 'The product contains no prerecorded audio-only or video-only content. The AI tutor\'s spoken replies in Voice are generated on demand and also displayed as on-screen text.'),
 ('1.2.2 Captions (Prerecorded)', 'A 2.0, 2.1, 2.2', NA, 'The product contains no prerecorded synchronized media (video).'),
 ('1.2.3 Audio Description or Media Alternative (Prerecorded)', 'A 2.0, 2.1, 2.2', NA, 'The product contains no prerecorded video.'),
 ('1.3.1 Info and Relationships', 'A 2.0, 2.1, 2.2', S, 'Uses header, nav and main landmarks; a heading on every screen and headings for sections and scored feedback; programmatic labels on all form fields; native lists; and aria-pressed / aria-current for selected toggles, topics and navigation items.'),
 ('1.3.2 Meaningful Sequence', 'A 2.0, 2.1, 2.2', S, 'DOM reading order matches the visual order on desktop and mobile layouts.'),
 ('1.3.3 Sensory Characteristics', 'A 2.0, 2.1, 2.2', S, 'Instructions refer to labeled controls, not to shape, size, color or location alone.'),
 ('1.4.1 Use of Color', 'A 2.0, 2.1, 2.2', S, 'Quiz results mark correct and incorrect answers with symbols (✓ / ✗) and text, not color alone. Selected states use fill, border and font-weight changes, plus programmatic state. Word-count guidance is stated in text.'),
 ('1.4.2 Audio Control', 'A 2.0, 2.1, 2.2', S, 'Audio plays only after a user action (Voice tutor reply, playback of the user\'s own recording) and can be stopped with the same control or the native player controls.'),
 ('2.1.1 Keyboard', 'A 2.0, 2.1, 2.2', S, 'All functions work from the keyboard, including navigation, flashcard flip and rating, quiz answering, chat, essay entry, accent-character buttons, recording controls and the Voice microphone button. Verified by scripted keyboard tests.'),
 ('2.1.2 No Keyboard Trap', 'A 2.0, 2.1, 2.2', S, 'Focus can always be moved away from every component using standard keys.'),
 ('2.1.4 Character Key Shortcuts', 'A 2.1, 2.2', NA, 'The product does not implement single-character keyboard shortcuts.'),
 ('2.2.1 Timing Adjustable', 'A 2.0, 2.1, 2.2', S, 'The product has no time limits. The writing timer counts up for the learner\'s information only and never ends a task. The BTLPT "approximately 25 minutes" note is guidance only. University sign-on session length is governed by Texas A&M CAS, outside this product.'),
 ('2.2.2 Pause, Stop, Hide', 'A 2.0, 2.1, 2.2', S, 'Animation appears only while content loads or while the microphone is actively listening, and it stops automatically. There is no auto-updating or scrolling content.'),
 ('2.3.1 Three Flashes or Below Threshold', 'A 2.0, 2.1, 2.2', S, 'No content flashes.'),
 ('2.4.1 Bypass Blocks', 'A 2.0, 2.1, 2.2', S, 'A "Skip to main content" link is the first focusable element, and landmarks are provided.'),
 ('2.4.2 Page Titled', 'A 2.0, 2.1, 2.2', S, 'The page title is "Avanza Español — Spanish for Texas Teachers". Each screen also exposes a heading naming the active screen.'),
 ('2.4.3 Focus Order', 'A 2.0, 2.1, 2.2', S, 'Focus order is logical. When content is replaced, focus moves to the new content: the next quiz question, the "Next question" button after answering, and the next flashcard after rating.'),
 ('2.4.4 Link Purpose (In Context)', 'A 2.0, 2.1, 2.2', S, 'Links and link-styled buttons have descriptive text.'),
 ('2.5.1 Pointer Gestures', 'A 2.1, 2.2', S, 'No multipoint or path-based gestures are required.'),
 ('2.5.2 Pointer Cancellation', 'A 2.1, 2.2', S, 'Actions fire on the up-event (standard click).'),
 ('2.5.3 Label in Name', 'A 2.1, 2.2', S, 'Accessible names contain the visible label text.'),
 ('2.5.4 Motion Actuation', 'A 2.1, 2.2', NA, 'No functions are operated by device motion.'),
 ('3.1.1 Language of Page', 'A 2.0, 2.1, 2.2', S, 'The document language is set to English (lang="en").'),
 ('3.2.1 On Focus', 'A 2.0, 2.1, 2.2', S, 'Receiving focus does not trigger a change of context.'),
 ('3.2.2 On Input', 'A 2.0, 2.1, 2.2', S, 'Changing a setting (e.g., proficiency level) updates the content in place and does not trigger an unexpected change of context.'),
 ('3.2.6 Consistent Help', 'A 2.2', NA, 'The product does not currently provide a help mechanism that repeats across screens. Support contact information is provided through program training materials.'),
 ('3.3.1 Error Identification', 'A 2.0, 2.1, 2.2', S, 'Errors (e.g., microphone permission denied, grading failure, content load failure) are described in text and announced to assistive technology.'),
 ('3.3.2 Labels or Instructions', 'A 2.0, 2.1, 2.2', S, 'All inputs have visible labels or instructions and programmatic labels.'),
 ('3.3.7 Redundant Entry', 'A 2.2', S, 'Users are not asked to re-enter information they already provided. A teacher-written prompt is pre-filled when edited.'),
 ('4.1.1 Parsing', 'A 2.0, 2.1', S, 'For WCAG 2.0 and 2.1, this criterion is treated as always supported, per the WCAG 2.2 errata (4.1.1 is obsolete and removed in WCAG 2.2). The application is rendered by React, which produces well-formed markup.'),
 ('4.1.2 Name, Role, Value', 'A 2.0, 2.1, 2.2', S, 'Native controls are used throughout. The flashcard is exposed as a button with keyboard support. Toggle and selection states are exposed with aria-pressed / aria-current.'),
]

LEVEL_AA = [
 ('1.2.4 Captions (Live)', 'AA 2.0, 2.1, 2.2', NA, 'The product contains no live synchronized media.'),
 ('1.2.5 Audio Description (Prerecorded)', 'AA 2.0, 2.1, 2.2', NA, 'The product contains no prerecorded video.'),
 ('1.3.4 Orientation', 'AA 2.1, 2.2', S, 'Content works in portrait and landscape and is not locked to either.'),
 ('1.3.5 Identify Input Purpose', 'AA 2.1, 2.2', NA, 'The product has no fields that collect information about the user. Sign-in is handled by Texas A&M CAS.'),
 ('1.4.3 Contrast (Minimum)', 'AA 2.0, 2.1, 2.2', S, 'All text meets 4.5:1 (large text 3:1). Automated contrast checks report no failures on any screen. Disabled controls and logos are exempt.'),
 ('1.4.4 Resize Text', 'AA 2.0, 2.1, 2.2', S, 'Text can be zoomed to 200% using browser zoom without loss of content or function. The layout switches to a single-column mobile layout.'),
 ('1.4.5 Images of Text', 'AA 2.0, 2.1, 2.2', S, 'No images of text are used, other than the Texas A&M logo (a logotype, which is exempt).'),
 ('1.4.10 Reflow', 'AA 2.1, 2.2', S, 'Verified at 320 CSS px width: no two-dimensional scrolling, and all functions (including the interface language switch) remain available. At narrow widths the navigation becomes a horizontally scrollable tab strip.'),
 ('1.4.11 Non-text Contrast', 'AA 2.1, 2.2', S, 'Input borders, control borders and the 3px focus indicator meet 3:1 against adjacent colors.'),
 ('1.4.12 Text Spacing', 'AA 2.1, 2.2', S, 'Tested with the WCAG text-spacing overrides (line height 1.5, letter spacing 0.12em, word spacing 0.16em, paragraph spacing 2em). No content was clipped or lost.'),
 ('1.4.13 Content on Hover or Focus', 'AA 2.1, 2.2', S, 'No custom hover or focus pop-ups are used. The only tooltips are native browser tooltips (title attribute).'),
 ('2.4.5 Multiple Ways', 'AA 2.0, 2.1, 2.2', NA, 'The product is a single-page application. Every screen is reachable directly from the persistent navigation.'),
 ('2.4.6 Headings and Labels', 'AA 2.0, 2.1, 2.2', S, 'Headings and labels describe their topic or purpose.'),
 ('2.4.7 Focus Visible', 'AA 2.0, 2.1, 2.2', S, 'A 3px high-contrast focus outline is shown on all focusable elements during keyboard navigation.'),
 ('2.4.11 Focus Not Obscured (Minimum)', 'AA 2.2', S, 'No sticky or overlay content covers the focused element.'),
 ('2.5.7 Dragging Movements', 'AA 2.2', NA, 'No dragging movements are used.'),
 ('2.5.8 Target Size (Minimum)', 'AA 2.2', S, 'Interactive targets are at least 24×24 CSS px or have enough spacing.'),
 ('3.1.2 Language of Parts', 'AA 2.0, 2.1, 2.2', PS, 'Spanish learning content is marked lang="es": tutor messages, quiz sentences, options, passages and feedback, flashcard words and examples, task prompts, transcriptions and essays. The sidebar and header follow the selected interface language. Exceptions: (1) when the interface language is set to Español, some interface labels within screens are not marked as Spanish; (2) mixed-language topic names (e.g., "Casos legales de Texas") and free-text learner input (which may be in either language) are not marked.'),
 ('3.2.3 Consistent Navigation', 'AA 2.0, 2.1, 2.2', S, 'The navigation is persistent and in the same order on every screen.'),
 ('3.2.4 Consistent Identification', 'AA 2.0, 2.1, 2.2', S, 'Components with the same function are identified consistently.'),
 ('3.3.3 Error Suggestion', 'AA 2.0, 2.1, 2.2', S, 'Error messages suggest corrections (e.g., allow microphone access, try again, minimum word count).'),
 ('3.3.4 Error Prevention (Legal, Financial, Data)', 'AA 2.0, 2.1, 2.2', NA, 'The product has no legal commitments, financial transactions, or modification or deletion of user-controllable stored data.'),
 ('3.3.8 Accessible Authentication (Minimum)', 'AA 2.2', S, 'Authentication uses Texas A&M NetID single sign-on (CAS), which supports password managers and paste. The product adds no cognitive function test.'),
 ('4.1.3 Status Messages', 'AA 2.1, 2.2', S, 'Loading, grading, quiz feedback, Voice status, copy confirmations and new chat messages are announced through status, log and alert live regions without moving focus.'),
]

def table(rows, caption):
    body = ''.join(f'<tr><td>{escape(c)} <span class="lvl">(Level {escape(v)})</span></td><td>{escape(s)}</td><td>{escape(r)}</td></tr>' for c, v, s, r in rows)
    return f'<h3>{caption}</h3><table><thead><tr><th style="width:30%">Criteria</th><th style="width:16%">Conformance Level</th><th>Remarks and Explanations</th></tr></thead><tbody>{body}</tbody></table>'

html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Avanza Español Accessibility Conformance Report</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 10.5pt; color: #111; line-height: 1.4; max-width: 960px; margin: 24px auto; padding: 0 16px; }}
h1 {{ font-size: 18pt; color: #500000; margin: 0 0 4px; }}
h2 {{ font-size: 14pt; color: #500000; border-bottom: 2px solid #500000; padding-bottom: 3px; margin-top: 26px; }}
h3 {{ font-size: 12pt; margin: 18px 0 6px; }}
table {{ border-collapse: collapse; width: 100%; margin: 6px 0 12px; }}
th, td {{ border: 1px solid #777; padding: 5px 7px; vertical-align: top; text-align: left; }}
th {{ background: #500000; color: #fff; }}
tbody tr:nth-child(even) td {{ background: #f6f2f2; }}
.lvl {{ color: #444; font-size: 9pt; }}
.sub {{ font-size: 11pt; margin: 0 0 16px; }}
dt {{ font-weight: bold; margin-top: 6px; }} dd {{ margin: 0 0 0 16px; }}
@media print {{ body {{ margin: 0; max-width: none; }} tr {{ page-break-inside: avoid; }} }}
</style></head><body>
<h1>Avanza Español Accessibility Conformance Report</h1>
<p class="sub"><strong>WCAG Edition</strong> (Based on VPAT<sup>®</sup> Version 2.5Rev, April 2025)</p>

<table><tbody>
<tr><th scope="row" style="width:30%">Name of Product/Version</th><td>Avanza Español v1.0 (Beta)</td></tr>
<tr><th scope="row">Report Date</th><td>September 30, 2026</td></tr>
<tr><th scope="row">Product Description</th><td>Avanza Español is a web application developed at Texas A&amp;M University. It uses artificial intelligence to support Spanish language learning and proficiency assessment for educators pursuing bilingual certification and endorsement pathways (BTLPT preparation). It provides AI-generated practice and assessment in listening, speaking, reading and writing, including text chat with an AI tutor, vocabulary flashcards, grammar and reading quizzes, graded writing and speaking tasks, voice conversation, and progress tracking.</td></tr>
<tr><th scope="row">Contact Information</th><td>Dr. Rafael Lara-Alecio (Resource Owner), Educational Psychology, College of Education and Human Development — a-lara@tamu.edu<br>Alternate: Dr. Beverly Irby — beverly.irby@tamu.edu<br>Center for Research and Development in Dual Language and Literacy Acquisition (CRDLLA), Texas A&amp;M University</td></tr>
<tr><th scope="row">Notes</th><td>
<p>This report covers the authenticated web application: navigation, Chat, Cards, Grammar Quiz, Reading, Writing (Opinion, Correspondence, Lesson Plan), Graded Speaking, BTLPT Oral Tasks, Voice and Progress. The Texas A&amp;M CAS sign-in pages are operated by Texas A&amp;M Technology Services and are outside the scope of this report. The "Listening" section is not yet released.</p>
<p><strong>Speech-based features.</strong> Voice, Graded Speaking and BTLPT Oral Tasks assess or practice spoken Spanish, so they require a microphone and the ability to speak. This is fundamental to evaluating oral proficiency. Text-based alternatives for practice are available in Chat and Writing, and accommodations are provided case by case. Voice speech recognition depends on the browser's Web Speech API (Chrome or Edge).</p>
<p><strong>AI-generated content.</strong> Prompts, feedback and tutor replies are generated by a large language model and rendered as plain text, lists and headings by the application.</p>
</td></tr>
<tr><th scope="row">Evaluation Methods Used</th><td>
<p>Evaluated by the development team in September 2026 against WCAG 2.2 Level A and AA (which includes all WCAG 2.0 and 2.1 A/AA criteria). Methods:</p>
<ul>
<li>Source-code review of every user-facing screen and component (React front end).</li>
<li>Automated testing with axe-core 4.10 (rule sets wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa) in Chromium on every screen, including interactive states (quiz question and answered states, flipped flashcard, generated writing/speaking prompts), at 1280px, 375px and 320px viewport widths. Result: 0 violations.</li>
<li>Scripted keyboard-only tests: skip link, navigation, flashcard flip and rating, quiz answering and focus management.</li>
<li>Reflow check at 320 CSS px and the WCAG 1.4.12 text-spacing override test.</li>
<li>Manual color-contrast calculation for all text and UI component colors.</li>
</ul>
<p>Browsers: Google Chrome (current). Manual screen-reader testing (VoiceOver on macOS, NVDA on Windows) is part of the ongoing evaluation and will be reflected in the next revision of this report.</p>
</td></tr>
</tbody></table>

<h2>Applicable Standards/Guidelines</h2>
<table><thead><tr><th>Standard/Guideline</th><th>Included In Report</th></tr></thead><tbody>
<tr><td>Web Content Accessibility Guidelines 2.0</td><td>Level A (Yes)<br>Level AA (Yes)<br>Level AAA (No)</td></tr>
<tr><td>Web Content Accessibility Guidelines 2.1</td><td>Level A (Yes)<br>Level AA (Yes)<br>Level AAA (No)</td></tr>
<tr><td>Web Content Accessibility Guidelines 2.2</td><td>Level A (Yes)<br>Level AA (Yes)<br>Level AAA (No)</td></tr>
</tbody></table>

<h2>Terms</h2>
<dl>
<dt>Supports</dt><dd>The functionality of the product has at least one method that meets the criterion without known defects or meets with equivalent facilitation.</dd>
<dt>Partially Supports</dt><dd>Some functionality of the product does not meet the criterion.</dd>
<dt>Does Not Support</dt><dd>The majority of product functionality does not meet the criterion.</dd>
<dt>Not Applicable</dt><dd>The criterion is not relevant to the product.</dd>
<dt>Not Evaluated</dt><dd>The product has not been evaluated against the criterion. This can only be used in WCAG Level AAA criteria.</dd>
</dl>

<h2>WCAG 2.x Report</h2>
{table(LEVEL_A, 'Table 1: Success Criteria, Level A')}
{table(LEVEL_AA, 'Table 2: Success Criteria, Level AA')}
<h3>Table 3: Success Criteria, Level AAA</h3>
<p>Not Evaluated.</p>

<h2>Remediation Plan</h2>
<table><thead><tr><th style="width:30%">Item</th><th style="width:16%">Criterion</th><th>Plan and Target Date</th></tr></thead><tbody>
<tr><td>Mark Spanish interface labels within screens when the interface language is set to Español, and mark mixed-language topic names</td><td>3.1.2</td><td>Target: December 31, 2026</td></tr>
<tr><td>Manual screen-reader verification (VoiceOver, NVDA) and publication of a revised ACR</td><td>All</td><td>Target: December 31, 2026</td></tr>
<tr><td>Add a consistent in-app help/contact link for accessibility support</td><td>3.2.6 (best practice)</td><td>Target: December 31, 2026</td></tr>
</tbody></table>
<p>Accessibility issues identified by users can be reported to the contacts above. They will be addressed through remediation or a timely, comparable alternative, in coordination with Texas A&amp;M Disability Resources and University Human Resources as appropriate.</p>

<h2>Legal Disclaimer</h2>
<p>This Accessibility Conformance Report describes the conformance of Avanza Español v1.0 (Beta) as evaluated on the report date. It was prepared by the product's development team at Texas A&amp;M University (CRDLLA) in good faith, based on the evaluation methods listed above. Later versions of the product may differ, and this report will be updated as the product changes. "VPAT" is a registered service mark of the Information Technology Industry Council (ITI).</p>
</body></html>'''

open('Avanza_Espanol_v1.0_ACR.html', 'w').write(html)
print('ok')
