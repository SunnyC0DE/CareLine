import { PipecatClient } from "@pipecat-ai/client-js";
import { ProtobufFrameSerializer, WebSocketTransport } from "@pipecat-ai/websocket-transport";
import "./style.css";

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) throw new Error("Careline app root not found.");

app.innerHTML = `
  <main class="page-shell">
    <header class="topbar">
      <a class="brand" href="/" aria-label="Careline home">
        <svg class="brand-mark" viewBox="0 0 42 42" aria-hidden="true">
          <path d="M8 35V10.5A3.5 3.5 0 0 1 11.5 7H30a4 4 0 0 1 4 4v24" />
          <path d="M15 35V19a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v16M19 24h8M23 20v8" />
          <path d="M5 35h32" />
        </svg>
        <span>careline</span>
      </a>
      <span class="demo-label">DEMO RECEPTION</span>
    </header>

    <section class="intro" aria-labelledby="page-title">
      <p id="clinic-name" class="eyebrow">CLINIC VOICE DESK</p>
      <h1 id="page-title">How can we help<br /><em>today?</em></h1>
      <p class="intro-copy">Ask about the clinic or let us help with an appointment. Speak naturally; you can interrupt at any time.</p>
    </section>

    <section class="conversation" aria-label="Voice conversation">
      <div class="conversation-head">
        <div>
          <p class="eyebrow">YOUR CONVERSATION</p>
          <p id="status" class="status-line" role="status" aria-live="polite">Ready when you are</p>
        </div>
        <span id="connection-dot" class="connection-dot" aria-hidden="true"></span>
      </div>

      <div class="voice-stage">
        <div class="orbit orbit-one"></div>
        <div class="orbit orbit-two"></div>
        <button id="talk-button" class="talk-button" type="button" aria-label="Start voice conversation">
          <svg id="mic-icon" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="9" y="2.5" width="6" height="12" rx="3" />
            <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v3.5M8.5 21.5h7" />
          </svg>
        </button>
        <p id="voice-hint" class="voice-hint">Tap to talk</p>
      </div>

      <div id="transcript" class="transcript" aria-live="polite" aria-label="Conversation transcript">
        <p class="transcript-empty">Your conversation will appear here.</p>
      </div>

      <div class="privacy-note">
        <span class="privacy-symbol" aria-hidden="true">i</span>
        <p>Training demo only. Please don’t share real patient or medical information. Emergencies require your local emergency service.</p>
      </div>
    </section>

    <aside class="clinic-rail" aria-label="Clinic details">
      <div class="rail-heading"><span class="rail-spark" aria-hidden="true">✳</span><span>AT A GLANCE</span></div>
      <div class="rail-item"><span class="rail-label">OPEN</span><strong id="working-days">Loading schedule</strong><span id="open-hours">Please wait</span></div>
      <div class="rail-item"><span class="rail-label">VISITS</span><strong id="visit-length">Loading</strong><span>By appointment</span></div>
      <div class="rail-item"><span class="rail-label">NEED A PERSON?</span><strong>We can request a follow-up</strong><span>This demo does not connect to live staff.</span></div>
      <p class="rail-footer">A calmer front desk, one conversation at a time.</p>
    </aside>

    <footer class="footer"><span>CARELINE · ENGLISH DEMO</span><span>NOT FOR REAL PATIENT BOOKINGS</span></footer>
  </main>
`;

const talkButton = document.querySelector<HTMLButtonElement>("#talk-button")!;
const statusLine = document.querySelector<HTMLParagraphElement>("#status")!;
const voiceHint = document.querySelector<HTMLParagraphElement>("#voice-hint")!;
const transcript = document.querySelector<HTMLDivElement>("#transcript")!;
const connectionDot = document.querySelector<HTMLSpanElement>("#connection-dot")!;
const clinicName = document.querySelector<HTMLParagraphElement>("#clinic-name")!;
const workingDays = document.querySelector<HTMLElement>("#working-days")!;
const openHours = document.querySelector<HTMLElement>("#open-hours")!;
const visitLength = document.querySelector<HTMLElement>("#visit-length")!;
let client: PipecatClient | null = null;
let connected = false;

interface PublicClinicConfig {
  clinic_name: string;
  working_days: string[];
  open_time: string;
  close_time: string;
  lunch_start: string;
  lunch_end: string;
  appointment_minutes: number;
}

function formatClock(value: string): string {
  const [hour = 0, minute = 0] = value.split(":").map(Number);
  const hour12 = hour % 12 || 12;
  const suffix = hour < 12 ? "AM" : "PM";
  return minute === 0 ? `${hour12} ${suffix}` : `${hour12}:${String(minute).padStart(2, "0")} ${suffix}`;
}

async function loadClinicConfig(): Promise<void> {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) throw new Error("Clinic settings are unavailable.");
    const config = (await response.json()) as PublicClinicConfig;
    clinicName.textContent = `${config.clinic_name} · VOICE DESK`;
    workingDays.textContent = config.working_days.join(", ");
    openHours.textContent = `${formatClock(config.open_time)}–${formatClock(config.lunch_start)} · ${formatClock(config.lunch_end)}–${formatClock(config.close_time)}`;
    visitLength.textContent = `${config.appointment_minutes} minutes`;
  } catch {
    clinicName.textContent = "Clinic details unavailable";
    workingDays.textContent = "Not available";
    openHours.textContent = "Please contact the clinic";
    visitLength.textContent = "Not available";
  }
}

void loadClinicConfig();

function setStatus(status: string, hint: string, active = false): void {
  statusLine.textContent = status;
  voiceHint.textContent = hint;
  connectionDot.classList.toggle("active", active);
  talkButton.classList.toggle("active", active);
  talkButton.setAttribute("aria-label", active ? "Stop voice conversation" : "Start voice conversation");
  talkButton.title = active ? "Stop voice conversation" : "Start voice conversation";
}

function appendTranscript(speaker: "You" | "Careline", text: string): void {
  const cleanText = text.trim();
  if (!cleanText) return;
  transcript.querySelector(".transcript-empty")?.remove();
  const entry = document.createElement("div");
  entry.className = `transcript-entry ${speaker === "You" ? "user-entry" : "assistant-entry"}`;
  const label = document.createElement("span");
  label.className = "speaker-label";
  label.textContent = speaker;
  const body = document.createElement("p");
  body.textContent = cleanText;
  entry.append(label, body);
  transcript.append(entry);
  transcript.scrollTop = transcript.scrollHeight;
}

async function stopConversation(): Promise<void> {
  if (client) {
    try {
      await client.disconnect();
    } finally {
      client = null;
      connected = false;
      setStatus("Conversation ended", "Tap to talk");
    }
  }
}

async function startConversation(): Promise<void> {
  setStatus("Connecting to the voice desk…", "Allow microphone access when asked");
  talkButton.disabled = true;
  try {
    const transport = new WebSocketTransport({
      serializer: new ProtobufFrameSerializer(),
      recorderSampleRate: 16000,
      playerSampleRate: 24000,
    });
    client = new PipecatClient({
      transport,
      enableMic: true,
      enableCam: false,
      callbacks: {
        onConnected: () => {
          connected = true;
          setStatus("Listening", "Speak when you’re ready", true);
        },
        onDisconnected: () => {
          connected = false;
          if (client) setStatus("Connection closed", "Tap to reconnect");
        },
        onUserTranscript: (data) => {
          if (data.final) appendTranscript("You", data.text);
        },
        onBotTranscript: (data) => appendTranscript("Careline", data.text),
        onBotStartedSpeaking: () => setStatus("Careline is speaking", "You can speak to interrupt", true),
        onBotStoppedSpeaking: () => setStatus("Listening", "Speak when you’re ready", true),
        onError: (error) => {
          console.error("Careline voice connection error", error);
          setStatus("Voice connection needs attention", "Check your connection, then try again");
        },
      },
    });
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    await client.connect({ wsUrl: `${protocol}//${window.location.host}/ws` });
    if (!connected) setStatus("Listening", "Speak when you’re ready", true);
  } catch (error) {
    console.error("Careline voice connection failed", error);
    setStatus("Couldn’t start the voice desk", "Check mic permission and provider setup");
    if (client) {
      try {
        await client.disconnect();
      } catch {
        // A failed connection may already have closed the transport.
      }
      client = null;
    }
  } finally {
    talkButton.disabled = false;
  }
}

talkButton.addEventListener("click", async () => {
  if (connected) await stopConversation();
  else if (client) await stopConversation();
  else await startConversation();
});
