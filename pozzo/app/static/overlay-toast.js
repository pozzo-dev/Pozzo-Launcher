// suoni generati con WebAudio: nessun file audio
const TONES = { soft: [[660, 0, .18], [880, .14, .28]], classic: [[523, 0, .12], [659, .12, .12], [784, .24, .12], [1047, .36, .4]] };
let audioCtx = null;

function beep(kind) {
  const seq = TONES[kind]; if (!seq) return;
  try {
    const Ctor = window.AudioContext || window.webkitAudioContext;
    if (!Ctor) return;
    if (!audioCtx || audioCtx.state === "closed") audioCtx = new Ctor();
    if (audioCtx.state === "suspended") audioCtx.resume().catch(() => {});
    const g = audioCtx.createGain(); g.gain.value = .12; g.connect(audioCtx.destination);
    seq.forEach(([f, at, len]) => {
      const o = audioCtx.createOscillator();
      o.type = kind === "soft" ? "sine" : "square";
      o.frequency.value = f;
      o.connect(g);
      o.start(audioCtx.currentTime + at);
      o.stop(audioCtx.currentTime + at + len);
    });
  } catch (e) {}
}

function safeIconUrl(u) {
  if (typeof u !== "string") return "";
  const s = u.trim();
  if (!s) return "";
  if (s.startsWith("/") && !s.startsWith("//")) return s;
  try {
    const p = new URL(s);
    return p.protocol === "http:" || p.protocol === "https:" ? p.href : "";
  } catch { return ""; }
}

const iconEl = document.getElementById("i");
if (iconEl) iconEl.onerror = () => { iconEl.hidden = true; iconEl.removeAttribute("src"); };

window.showToast = async (x) => {
  if (window.GSI18n?.ready) await window.GSI18n.ready;
  x = x || {};
  document.getElementById("k").textContent = (x.key && window.t ? t(x.key) : x.title) || "";
  document.getElementById("n").textContent = x.text || "";
  document.getElementById("d").textContent = x.desc || "";
  const icon = safeIconUrl(x.icon);
  const i = document.getElementById("i");
  i.hidden = !icon;
  if (icon) i.src = icon; else i.removeAttribute("src");
  const box = document.getElementById("t");
  box.classList.remove("on");
  void box.offsetWidth;
  box.classList.add("on");
  beep(x.sound);
};
