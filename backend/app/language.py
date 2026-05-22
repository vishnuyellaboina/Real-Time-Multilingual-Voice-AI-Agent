from __future__ import annotations

from .models import LanguageCode


HINDI_MARKERS = {"नमस्ते", "डॉक्टर", "बुक", "अपॉइंटमेंट", "कल", "आज", "शाम", "सुबह", "रद्द"}
TAMIL_MARKERS = {"வணக்கம்", "மருத்துவர்", "மாலை", "காலை", "நாளை", "இன்று", "பதிவு", "ரத்து"}


def detect_language(text: str, preferred: LanguageCode | None = None) -> LanguageCode:
    lowered = text.lower()
    if any(marker in text for marker in TAMIL_MARKERS):
        return "ta"
    if any(marker in text for marker in HINDI_MARKERS):
        return "hi"
    if preferred:
        return preferred
    if any(ch in text for ch in "ஃஅஆஇஈஉஊஎஏஐஒஓகஙசஜஞடணதநபமயரலவழளறன"):
        return "ta"
    if any("\u0900" <= ch <= "\u097f" for ch in text):
        return "hi"
    return "en"


def render_text(language: LanguageCode, key: str, **kwargs: str) -> str:
    templates = {
        "en": {
            "booked": "Your appointment with {doctor} is booked for {slot}.",
            "alternatives": "That slot is not available. I can offer {options}.",
            "cancelled": "Your appointment on {slot} has been cancelled.",
            "rescheduled": "Your appointment has been moved to {slot} with {doctor}.",
            "not_found": "I could not find an active appointment. Please tell me the doctor or date.",
            "campaign_intro": "Hello {name}, I am calling from 2care about your appointment.",
            "fallback": "I can help with booking, rescheduling, cancellation, or reminders. What would you like to do?",
        },
        "hi": {
            "booked": "{doctor} के साथ आपका अपॉइंटमेंट {slot} के लिए बुक हो गया है।",
            "alternatives": "वह समय उपलब्ध नहीं है। मैं {options} ऑफर कर सकता हूँ।",
            "cancelled": "{slot} वाला आपका अपॉइंटमेंट रद्द कर दिया गया है।",
            "rescheduled": "आपका अपॉइंटमेंट {doctor} के साथ {slot} पर बदल दिया गया है।",
            "not_found": "मुझे कोई सक्रिय अपॉइंटमेंट नहीं मिला। कृपया डॉक्टर या तारीख बताइए।",
            "campaign_intro": "नमस्ते {name}, मैं 2care से आपके अपॉइंटमेंट के बारे में कॉल कर रहा हूँ।",
            "fallback": "मैं बुकिंग, रीशेड्यूल, कैंसलेशन या रिमाइंडर में मदद कर सकता हूँ। आपको क्या करना है?",
        },
        "ta": {
            "booked": "{doctor} உடன் உங்கள் நேரம் {slot}க்கு பதிவு செய்யப்பட்டது.",
            "alternatives": "அந்த நேரம் கிடைக்கவில்லை. {options} நேரங்களை வழங்க முடியும்.",
            "cancelled": "{slot} நேர நியமனம் ரத்து செய்யப்பட்டது.",
            "rescheduled": "{doctor} உடன் உங்கள் நேரம் {slot}க்கு மாற்றப்பட்டது.",
            "not_found": "செயலில் உள்ள நியமனம் கிடைக்கவில்லை. மருத்துவர் அல்லது தேதியை சொல்லுங்கள்.",
            "campaign_intro": "வணக்கம் {name}, 2care இலிருந்து உங்கள் நேரம் குறித்து அழைக்கிறேன்.",
            "fallback": "பதிவு, மாற்றம், ரத்து அல்லது நினைவூட்டலில் உதவலாம். என்ன செய்ய வேண்டும்?",
        },
    }
    return templates[language][key].format(**kwargs)

