// Dirette Twitch e video YouTube nella scheda del gioco. Senza chiavi spiega cosa offre e come attivarlo,
// con una ricerca su YouTube che funziona subito; le chiavi si mettono in Impostazioni › Streaming › Dirette e video.
const P = "/plugin-api/twitch-youtube";
const SEC = "dirette-video";
const TAB = "twitch-youtube";
const TW_SEARCH = (q) => `https://www.twitch.tv/search?term=${encodeURIComponent(q)}`;
const YT_SEARCH = (q) => `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}`;

export default function (gs, ctx) {
  const { t, lang } = ctx;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const open = (url) => gs.api("/api/open", { body: { url } }).catch((err) => gs.toast(err.message, true));
  const btn = (text, fn, cls = "btn") => { const b = el("button", cls, text); b.type = "button"; b.onclick = fn; return b; };
  const toSettings = () => (typeof openSettings === "function" ? openSettings(`ext:${TAB}`) : null);

  gs.addTutorial({
    id: ctx.id, section: SEC,
    steps: [
      { title: t("tut.1.t"), text: t("tut.1.x"), sel: ".tv-box" },
      { title: t("tut.2.t"), text: t("tut.2.x"), sel: ".tv-setup, .tv-grid" },
    ],
  });

  function liveCard(s) {
    const c = el("button", "tv-card"); c.type = "button";
    c.onclick = () => open(s.url);
    const media = el("div", "tv-media");
    if (s.thumbnail) { const img = el("img", "tv-thumb"); img.loading = "lazy"; img.alt = ""; img.referrerPolicy = "no-referrer"; img.src = s.thumbnail; img.onerror = () => img.remove(); media.append(img); }
    media.append(el("span", "tv-live", t("live")), el("span", "tv-viewers", t("viewers", { n: s.viewers.toLocaleString(lang) })));
    c.append(media, el("b", "tv-title", s.title), el("small", "muted", s.user));
    return c;
  }

  function videoCard(v) {
    const c = el("div", "tv-card");
    const media = el("div", "tv-media");
    const img = el("img", "tv-thumb"); img.loading = "lazy"; img.alt = ""; img.referrerPolicy = "no-referrer"; img.src = v.thumb;
    const play = el("button", "tv-play", "▶"); play.type = "button"; play.setAttribute("aria-label", t("watch", { titolo: v.title }));
    play.onclick = () => {  // il video si carica solo al clic
      const f = el("iframe"); f.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(v.videoId)}?autoplay=1`;
      f.allow = "autoplay; encrypted-media; picture-in-picture"; f.allowFullscreen = true; f.title = v.title;
      media.replaceChildren(f);
    };
    media.append(img, play);
    const ext = btn(t("openYt"), () => open(`https://www.youtube.com/watch?v=${encodeURIComponent(v.videoId)}`), "tv-link");
    c.append(media, el("b", "tv-title", v.title), el("small", "muted", v.channel), ext);
    return c;
  }

  /** Riquadro di un servizio senza chiave: cosa offre, come attivarlo, e la ricerca nel browser che va gia'. */
  function setup(service, q) {
    const box = el("div", "tv-setup");
    box.append(el("b", "", t(`${service}.off.t`)), el("p", "muted", t(`${service}.off.x`)));
    const row = el("div", "row wrap");
    row.append(btn(t("setup"), toSettings, "btn primary"),
      btn(t(`${service}.search`), () => open(service === "tw" ? TW_SEARCH(q) : YT_SEARCH(`${q} ${t("q.trailer")}`))));
    box.append(row);
    return box;
  }

  async function block(box, service, q, on) {
    const head = el("div", "tv-head");
    head.append(el("h4", "", t(`${service}.title`)));
    const body = el("div");
    box.append(head, body);
    if (!on) return body.append(setup(service, q));
    body.append(el("p", "muted", t("loading")));
    try {
      const items = service === "tw" ? (await gs.api(`${P}/live/${encodeURIComponent(q)}`)).streams : (await gs.api(`${P}/videos/${encodeURIComponent(q)}`)).videos;
      body.replaceChildren();
      if (!items.length) body.append(el("p", "muted", t(`${service}.none`)));
      else { const grid = el("div", "tv-grid"); grid.append(...items.map(service === "tw" ? liveCard : videoCard)); body.append(grid); }
    } catch (e) { body.replaceChildren(el("p", "muted", e.message)); }
    head.append(btn(t(`${service}.more`), () => open(service === "tw" ? TW_SEARCH(q) : YT_SEARCH(q)), "tv-link"));
  }

  gs.addDetailSection({
    id: SEC,
    title: t("title"),
    async render(game) {
      const box = el("div", "tv-box");
      const q = game.title || "";
      let st;
      try { st = await gs.api(`${P}/stato`); } catch (e) { box.textContent = e.message; return box; }
      // YouTube prima: e' quello che si usa di piu' e con la chiave gratuita funziona per tutti i giochi
      await Promise.all([block(box, "yt", q, st.youtube), block(box, "tw", q, st.twitch)]);
      return box;
    },
  });

  async function renderSettings(root) {
      let st;
      try { st = await gs.api(`${P}/stato`); } catch (e) { root.textContent = e.message; return; }
      root.innerHTML = `<h3>${gs.esc(t("settings.title"))}</h3>
        <p class="muted">${gs.esc(t("settings.x"))}</p>
        <form class="tv-form">
          <fieldset><legend>YouTube <span class="badge">${gs.esc(st.youtube ? t("on") : t("off"))}</span></legend>
            <p class="muted small">${gs.esc(t("settings.yt"))} <button class="tv-link" type="button" data-url="https://console.cloud.google.com/apis/library/youtube.googleapis.com">console.cloud.google.com</button></p>
            <input class="field" name="youtube_key" type="password" autocomplete="off" placeholder="${gs.esc(t("settings.ytKey"))}" aria-label="${gs.esc(t("settings.ytKey"))}"></fieldset>
          <fieldset><legend>Twitch <span class="badge">${gs.esc(st.twitch ? t("on") : t("off"))}</span></legend>
            <p class="muted small">${gs.esc(t("settings.tw"))} <button class="tv-link" type="button" data-url="https://dev.twitch.tv/console/apps">dev.twitch.tv</button></p>
            <input class="field" name="twitch_client_id" autocomplete="off" placeholder="Client ID" aria-label="Twitch Client ID">
            <input class="field" name="twitch_client_secret" type="password" autocomplete="off" placeholder="Client Secret" aria-label="Twitch Client Secret"></fieldset>
          <p class="muted small">${gs.esc(t("settings.keep"))}</p>
          <button class="btn primary" type="submit">${gs.esc(t("save"))}</button></form>`;
      root.querySelectorAll("[data-url]").forEach((b) => { b.onclick = () => open(b.dataset.url); });
      root.querySelector("form").onsubmit = async (e) => {
        e.preventDefault();
        const f = new FormData(e.target);
        try { await gs.api(`${P}/impostazioni`, { body: Object.fromEntries(f) }); } catch (err) { return gs.toast(err.message, true); }
        gs.toast(t("saved"));
        renderSettings(root);
      };
  }
  gs.addSettingsTab({ id: TAB, label: t("settings.tab"), category: "streaming", render: renderSettings });
}
