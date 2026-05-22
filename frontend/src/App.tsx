import { useEffect, useRef, useState } from "react";

type Reply = {
  text: string;
  language: "en" | "hi" | "ta" | string;
  intent: string;
  latency: {
    total_ms: number;
    reasoning_ms: number;
    tool_ms: number;
    response_render_ms: number;
  };
  trace: Array<{ stage: string; detail: string; at: string }>;
  tool_calls: Array<{ name: string; rationale: string }>;
};

type ConversationTurn = {
  speaker: "patient" | "agent";
  text: string;
  language?: string;
};

type RecognitionCtor = new () => SpeechRecognition;

declare global {
  interface Window {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  }

  interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
  }

  interface SpeechRecognitionErrorEvent extends Event {
    error: string;
    message?: string;
  }

  interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
    start(): void;
    stop(): void;
  }
}

const presets = [
  {
    patientId: "P1001",
    label: "English booking",
    transcript: "Book an appointment with Dr Iyer tomorrow evening for follow up"
  },
  {
    patientId: "P1002",
    label: "Hindi reschedule",
    transcript: "मेरा अपॉइंटमेंट कल सुबह से शाम 4 बजे बदल दीजिए"
  },
  {
    patientId: "P1003",
    label: "Tamil booking",
    transcript: "நாளை காலை மருத்துவர் லக்ஷ்மியுடன் பதிவு செய்யுங்கள்"
  }
];

const speechLanguageMap: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  ta: "ta-IN"
};

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

function supportsBrowserVoice() {
  return (
    window.isSecureContext &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition) &&
    "speechSynthesis" in window
  );
}

function createRecognition() {
  const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export default function App() {
  const [patientId, setPatientId] = useState("P1001");
  const [transcript, setTranscript] = useState(presets[0].transcript);
  const [reply, setReply] = useState<Reply | null>(null);
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [channel, setChannel] = useState<"inbound" | "outbound">("inbound");
  const [campaignId, setCampaignId] = useState("CMP-REMINDER-001");
  const [speechState, setSpeechState] = useState<"idle" | "listening" | "speaking">("idle");
  const [selectedLocale, setSelectedLocale] = useState("en-IN");
  const [speechSupported, setSpeechSupported] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const transcriptRef = useRef(transcript);

  useEffect(() => {
    setSpeechSupported(supportsBrowserVoice());
    return () => {
      recognitionRef.current?.stop();
      window.speechSynthesis.cancel();
    };
  }, []);

  useEffect(() => {
    transcriptRef.current = transcript;
  }, [transcript]);

  function pushConversationTurn(turn: ConversationTurn) {
    setConversation((current) => [...current, turn]);
  }

  function stopVoiceOutput() {
    window.speechSynthesis.cancel();
    setSpeechState((current) => (current === "speaking" ? "idle" : current));
  }

  function speakReply(nextReply: Reply) {
    stopVoiceOutput();
    const utterance = new SpeechSynthesisUtterance(nextReply.text);
    utterance.lang = speechLanguageMap[nextReply.language] || selectedLocale;
    utterance.rate = 1;
    utterance.onstart = () => setSpeechState("speaking");
    utterance.onend = () => setSpeechState("idle");
    window.speechSynthesis.speak(utterance);
  }

  async function submitTurn(nextTranscript?: string) {
    const resolvedTranscript = nextTranscript ?? transcript;
    if (!resolvedTranscript.trim()) {
      setError("Please speak or enter a transcript before sending.");
      return;
    }

    setError(null);
    setLoading(true);
    pushConversationTurn({ speaker: "patient", text: resolvedTranscript, language: selectedLocale });

    try {
      const response = await fetch(`${apiBaseUrl}/api/turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          transcript: resolvedTranscript,
          channel,
          campaign_id: channel === "outbound" ? campaignId : null
        })
      });
      if (!response.ok) {
        throw new Error(`Backend request failed with ${response.status}`);
      }
      const data: Reply = await response.json();
      setReply(data);
      pushConversationTurn({ speaker: "agent", text: data.text, language: data.language });
      setSelectedLocale(speechLanguageMap[data.language] || selectedLocale);
      speakReply(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? `${requestError.message}. Check VITE_API_BASE_URL and backend deployment.`
          : "Could not reach the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  function startListening() {
    if (!speechSupported) {
      setError("Voice input requires Chrome or Edge over HTTPS or localhost. Use typed mode if browser speech is unavailable.");
      return;
    }

    stopVoiceOutput();
    recognitionRef.current?.stop();
    const recognition = createRecognition();
    if (!recognition) {
      setError("Speech recognition is unavailable in this browser.");
      return;
    }

    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = selectedLocale;

    recognition.onresult = (event) => {
      const nextTranscript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join(" ")
        .trim();
      setTranscript(nextTranscript);
      transcriptRef.current = nextTranscript;
    };

    recognition.onerror = (event) => {
      setSpeechState("idle");
      setError(`Speech recognition error: ${event.error}`);
    };

    recognition.onend = () => {
      setSpeechState("idle");
      const finalTranscript = transcriptRef.current.trim();
      if (finalTranscript) {
        void submitTurn(finalTranscript);
      }
    };

    recognitionRef.current = recognition;
    setSpeechState("listening");
    recognition.start();
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setSpeechState("idle");
  }

  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Real-time Multilingual Clinical Agent</p>
        <h1>Voice appointment agent demo</h1>
        <p className="lede">
          Browser microphone input, browser voice output, explicit backend tool orchestration, multilingual continuity, session memory,
          and latency traces for the full appointment lifecycle.
        </p>
      </section>

      <section className="card controls">
        <div className="inline-grid">
          <label>
            Patient ID
            <input value={patientId} onChange={(event) => setPatientId(event.target.value)} />
          </label>
          <label>
            Mode
            <select value={channel} onChange={(event) => setChannel(event.target.value as "inbound" | "outbound")}>
              <option value="inbound">Inbound</option>
              <option value="outbound">Outbound reminder</option>
            </select>
          </label>
          <label>
            Voice locale
            <select value={selectedLocale} onChange={(event) => setSelectedLocale(event.target.value)}>
              <option value="en-IN">English (India)</option>
              <option value="hi-IN">Hindi (India)</option>
              <option value="ta-IN">Tamil (India)</option>
            </select>
          </label>
        </div>

        {channel === "outbound" && (
          <label>
            Campaign ID
            <input value={campaignId} onChange={(event) => setCampaignId(event.target.value)} />
          </label>
        )}

        <label>
          Transcript
          <textarea rows={5} value={transcript} onChange={(event) => setTranscript(event.target.value)} />
        </label>

        <div className="actions">
          {presets.map((preset) => (
            <button
              key={preset.label}
              className="secondary"
              onClick={() => {
                setPatientId(preset.patientId);
                setTranscript(preset.transcript);
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="actions">
          <button onClick={speechState === "listening" ? stopListening : startListening} disabled={loading}>
            {speechState === "listening" ? "Stop listening" : "Start voice turn"}
          </button>
          <button className="secondary" onClick={() => submitTurn()} disabled={loading}>
            {loading ? "Thinking..." : "Send typed turn"}
          </button>
          <button className="secondary" onClick={stopVoiceOutput}>
            Stop agent voice
          </button>
        </div>

        <p className="status">
          <strong>Voice status:</strong> {speechSupported ? speechState : "unsupported"}{" "}
          {speechSupported ? `using browser speech APIs and ${apiBaseUrl}` : "use Chrome/Edge over HTTPS or typed mode"}
        </p>
        {error && <p className="error">{error}</p>}
      </section>

      <section className="grid">
        <article className="card">
          <h2>Conversation</h2>
          <div className="conversation">
            {conversation.length === 0 && <p className="muted">Start a voice turn or send a transcript to begin.</p>}
            {conversation.map((turn, index) => (
              <div key={`${turn.speaker}-${index}`} className={`bubble ${turn.speaker}`}>
                <p className="bubble-meta">{turn.speaker === "patient" ? "Patient" : "Agent"}</p>
                <p>{turn.text}</p>
              </div>
            ))}
          </div>
        </article>

        {reply && (
          <>
            <article className="card">
              <h2>Agent reply</h2>
              <p className="reply">{reply.text}</p>
              <p>
                <strong>Intent:</strong> {reply.intent} <strong>Language:</strong> {reply.language}
              </p>
            </article>

            <article className="card">
              <h2>Latency</h2>
              <p>Total: {reply.latency.total_ms} ms</p>
              <p>Reasoning: {reply.latency.reasoning_ms} ms</p>
              <p>Tools: {reply.latency.tool_ms} ms</p>
              <p>Render: {reply.latency.response_render_ms} ms</p>
            </article>

            <article className="card">
              <h2>Tool calls</h2>
              {reply.tool_calls.map((tool) => (
                <p key={`${tool.name}-${tool.rationale}`}>
                  <strong>{tool.name}</strong>: {tool.rationale}
                </p>
              ))}
            </article>

            <article className="card full">
              <h2>Reasoning trace</h2>
              {reply.trace.map((item) => (
                <p key={`${item.at}-${item.stage}`}>
                  <strong>{item.stage}</strong>: {item.detail}
                </p>
              ))}
            </article>
          </>
        )}
      </section>
    </main>
  );
}
