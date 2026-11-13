// Browser speech: recognition for push-to-talk Ask, synthesis for Listen. Feature-detected; no server audio.
export function canListen(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function canDictate(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as any;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

function indianVoice(): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  return voices.find((v) => v.lang === "en-IN") || voices.find((v) => v.lang.startsWith("en-"));
}

/** Speak parts in order; onPart(i) fires as each part starts so the UI can highlight it. */
export function speakParts(parts: string[], onPart: (i: number) => void, onEnd: () => void): () => void {
  const synth = window.speechSynthesis;
  synth.cancel();
  let stopped = false;
  parts.forEach((text, i) => {
    const u = new SpeechSynthesisUtterance(text);
    const v = indianVoice();
    if (v) u.voice = v;
    u.lang = v?.lang || "en-IN";
    u.rate = 1.02;
    u.onstart = () => !stopped && onPart(i);
    if (i === parts.length - 1) u.onend = () => !stopped && onEnd();
    synth.speak(u);
  });
  return () => { stopped = true; synth.cancel(); };
}

export function speak(text: string, onEnd?: () => void): () => void {
  return speakParts([text.replace(/\[\d+\]/g, "")], () => {}, onEnd || (() => {}));
}

/** Start dictation; returns a stop function. Results stream into onText (interim + final). */
export function dictate(onText: (t: string, final: boolean) => void, onEnd: () => void): () => void {
  const w = window as any;
  const Rec = w.SpeechRecognition || w.webkitSpeechRecognition;
  const rec = new Rec();
  rec.lang = "en-IN";
  rec.interimResults = true;
  rec.continuous = false;
  rec.onresult = (e: any) => {
    let text = "";
    let final = false;
    for (let i = 0; i < e.results.length; i++) {
      text += e.results[i][0].transcript;
      final = final || e.results[i].isFinal;
    }
    onText(text, final);
  };
  rec.onend = onEnd;
  rec.onerror = onEnd;
  rec.start();
  return () => rec.stop();
}
