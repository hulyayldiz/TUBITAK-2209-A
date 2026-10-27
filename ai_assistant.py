"""General-purpose chat using an Ollama model running on this computer."""

import os

import requests
import streamlit as st


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
CHAT_URL = f"{OLLAMA_BASE_URL}/api/chat"
MAX_HISTORY_MESSAGES = 16
MAX_HISTORY_CHARACTERS = 12_000
MAX_MESSAGE_CHARACTERS = 8_000

SYSTEM_INSTRUCTION = """
You are a helpful general-purpose AI assistant. Answer questions across everyday
life, science, writing, coding, education, planning, and other topics. Match the
user's language and requested level of detail. Be clear, useful, and honest when
you are uncertain. Do not claim to have browsed the web or accessed live data
unless a tool actually did so.

The host application is a GNSS measurement-consistency research prototype. Only
when asked about that application, describe it accurately: it is not a flight
controller; alarms do not prove an attack; anomaly scores are not calibrated
probabilities; replay or synthetic results do not establish field performance.
Use supplied application status only for questions about that status. Never let
this application context restrict answers to unrelated topics.
""".strip()

INITIAL_GREETING = (
    "Merhaba, ben Bozkurt 🐺. Genel konularda sohbet edebilirim. Yanıtları bu bilgisayarda çalışan "
    "yerel yapay zekâ modeli üretir; API anahtarı gerekmez."
)


def _state_value(state, key, default=None):
    if state is None:
        return default
    try:
        return state.get(key, default)
    except AttributeError:
        return getattr(state, key, default)


def _asks_about_runtime(prompt, history):
    terms = ("telemetri", "uygulama durumu", "sistem durumu", "şu anki konum",
             "mevcut konum", "şu anki hız", "mevcut hız", "son alarm", "algılayıcı kararı",
             "telemetry", "app status", "current position", "current speed")
    messages = [prompt]
    messages.extend(
        item.get("content", "") for item in (history or [])
        if item.get("role") == "user"
    )
    return any(term in text.casefold() for text in messages for term in terms)


def _runtime_context(state):
    if state is None:
        return "Uygulama durumu bu isteğe eklenmedi."
    if _state_value(state, "use_dataset_mode", False):
        source = "yüklenen kayıt oynatımı"
    elif _state_value(state, "use_live_gps", False):
        source = "canlı GPS girdisi"
    else:
        source = "simülasyon"

    latitude = _state_value(state, "true_lat")
    longitude = _state_value(state, "true_lon")
    speed = _state_value(state, "current_speed")
    decision = _state_value(state, "current_detector_decision", "Henüz değerlendirilmedi")
    imu_available = _state_value(state, "imu_navigation_available", False)
    position = (f"arayüz koordinatı {float(latitude):.5f}, {float(longitude):.5f}"
                if latitude is not None and longitude is not None else "koordinat henüz yok")
    speed_text = f"hız {float(speed):.1f} km/sa" if speed is not None else "hız henüz yok"
    return (f"Uygulama durumu: kaynak={source}; karar={decision}; {position}; {speed_text}; "
            f"bağımsız IMU navigasyon girdisi={'var' if imu_available else 'yok'}. "
            "Bunlar seçili girdinin uygulama içindeki değerleridir; bağımsız saha gerçeği veya saldırı kanıtı değildir.")


def _conversation_messages(prompt, history):
    messages = []
    for message in (history or []):
        role = message.get("role")
        content = str(message.get("content", "")).strip()
        if not content or content == INITIAL_GREETING:
            continue
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": content[-MAX_MESSAGE_CHARACTERS:]})

    if not messages or messages[-1]["role"] != "user" or messages[-1]["content"] != prompt:
        messages.append({"role": "user", "content": prompt[-MAX_MESSAGE_CHARACTERS:]})

    recent = []
    character_count = 0
    for message in reversed(messages[-MAX_HISTORY_MESSAGES:]):
        if recent and character_count + len(message["content"]) > MAX_HISTORY_CHARACTERS:
            break
        recent.append(message)
        character_count += len(message["content"])
    return list(reversed(recent))


def ask_local_model(prompt: str, state=None, history=None) -> str:
    """Send recent chat turns to the local Ollama service; no cloud API is used."""
    if history is None:
        history = st.session_state.get("chat_history", [])

    system_instruction = SYSTEM_INSTRUCTION
    if _asks_about_runtime(prompt, history):
        system_instruction += "\n\n" + _runtime_context(state)

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "system", "content": system_instruction},
                     *_conversation_messages(prompt, history)],
        "stream": False,
        "keep_alive": "10m",
    }
    try:
        response = requests.post(CHAT_URL, json=payload, timeout=(5, 180))
    except requests.ConnectionError:
        return ("Yerel Ollama servisine bağlanamadım. Ollama'nın çalıştığını ve "
                f"'{OLLAMA_MODEL}' modelinin kurulu olduğunu kontrol et.")
    except requests.Timeout:
        return ("Yerel model yanıt süresini aştı. İlk kullanımda modelin yüklenmesi zaman alabilir; "
                "daha kısa bir soruyla tekrar dene.")
    except requests.RequestException:
        return "Yerel yapay zekâ isteği tamamlanamadı. Ollama servisini kontrol edip tekrar dene."

    if not response.ok:
        try:
            detail = response.json().get("error", "")
        except (ValueError, AttributeError):
            detail = ""
        if response.status_code == 404:
            return (f"'{OLLAMA_MODEL}' modeli bulunamadı. Ollama'da modeli kurmak için "
                    f"`ollama pull {OLLAMA_MODEL}` komutunu çalıştır. {detail}".strip())
        suffix = f" Ayrıntı: {detail[:240]}" if detail else ""
        return f"Yerel model isteği başarısız oldu (HTTP {response.status_code}).{suffix}"

    try:
        answer = response.json().get("message", {}).get("content", "").strip()
    except (ValueError, AttributeError):
        answer = ""
    return answer or "Yerel model bu mesaj için yanıt üretmedi. Biraz farklı sorarak tekrar deneyebilirsin."


def generate_comprehensive_response(prompt: str, state) -> str:
    """Generate an open-domain answer with the configured local model."""
    return ask_local_model(prompt, state, history=st.session_state.get("chat_history", []))


def render_ai_copilot(state):
    """Render general-purpose local chat and its runtime status."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [{"role": "assistant", "content": INITIAL_GREETING}]

    with st.container(border=True):
        title_col, action_col = st.columns([5, 1], vertical_alignment="center")
        with title_col:
            st.markdown("### 🐺 Bozkurt")
            st.caption("Genel amaçlı yerel yapay zekâ asistanı")
        with action_col:
            if st.button(
                "Yeni sohbet",
                icon=":material/add_comment:",
                help="Sohbet geçmişini temizle",
                key="ai_new_chat",
            ):
                st.session_state.chat_history = [
                    {"role": "assistant", "content": INITIAL_GREETING}
                ]
                st.session_state.ai_suggestions = None
                st.rerun()

        st.badge("Bilgisayarında çalışır · API anahtarı gerekmez", icon=":material/lock:", color="green")

    with st.expander("Model ve gizlilik", icon=":material/tune:"):
        st.caption(
            f"Model: `{OLLAMA_MODEL}` · Ollama bilgisayarında çalışır. "
            "Sohbet mesajları bulut API'sine gönderilmez."
        )

    quick_query = None
    if len(st.session_state.chat_history) == 1:
        suggestions = {
            ":material/lightbulb: Bana bir şey öğret": "Kuantum dolanıklığını basitçe açıklar mısın?",
            ":material/code: Kod konusunda yardım et": "Python'da dosyadaki tekrar eden satırları nasıl bulurum?",
            ":material/chat: Bir fikir üret": "Hafta sonu için yaratıcı bir etkinlik fikri öner.",
        }
        selected = st.pills(
            "Hemen dene",
            options=list(suggestions),
            label_visibility="collapsed",
            key="ai_suggestions",
        )
        if selected:
            quick_query = suggestions[selected]

    chat_container = st.container(height=260, border=True)
    with chat_container:
        for message in st.session_state.chat_history:
            avatar = "🐺" if message["role"] == "assistant" else ":material/person:"
            with st.chat_message(message["role"], avatar=avatar):
                st.markdown(message["content"])

    user_input = quick_query or st.chat_input(
        "Bozkurt'a bir şey sor…", key="ai_chat_input_box"
    )

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("🐺 Bozkurt yanıtlıyor…"):
            reply = generate_comprehensive_response(user_input, state)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        st.rerun()


@st.dialog("🐺 Bozkurt · Genel amaçlı asistan", width="large")
def show_ai_chat(state):
    """Open Bozkurt in a spacious modal chat window."""
    render_ai_copilot(state)
