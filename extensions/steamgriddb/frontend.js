// SteamGridDB: scheda nelle impostazioni per la chiave dell'API. La fonte la usa lo scraping e il menu «Immagini del gioco…».
export default function (gs, ctx) {
  const { t } = ctx;
  async function draw(el) {
    let d;
    try { d = await gs.api("/plugin-api/steamgriddb/stato"); } catch (e) { el.textContent = e.message; return; }
    el.innerHTML = `<h3>SteamGridDB <span class="badge">${gs.esc(d.chiave ? t("on") : t("off"))}</span></h3>
      <p class="muted">${gs.esc(t("x"))}</p>
      <p class="muted small">${gs.esc(t("key"))} <button class="sg-link" type="button" data-url="https://www.steamgriddb.com/profile/preferences/api">steamgriddb.com › Preferences › API</button></p>
      <form class="row wrap sg-form"><input class="field" type="password" name="k" placeholder="${gs.esc(t("paste"))}" aria-label="${gs.esc(t("paste"))}" autocomplete="off">
        <button class="btn primary" type="submit">${gs.esc(t("save"))}</button>
        ${d.chiave ? `<button class="btn" type="button" id="sg-del">${gs.esc(t("remove"))}</button>` : ""}</form>
      <p class="muted small">${gs.esc(t("media"))}</p>`;
    el.querySelector("[data-url]").onclick = (e) => gs.api("/api/open", { body: { url: e.target.dataset.url } }).catch((err) => gs.toast(err.message, true));
    const set = async (chiave) => {
      try { await gs.api("/plugin-api/steamgriddb/chiave", { body: { chiave } }); gs.toast(t(chiave ? "saved" : "removed")); } catch (e) { return gs.toast(e.message, true); }
      draw(el);
    };
    el.querySelector("form").onsubmit = (e) => { e.preventDefault(); set(new FormData(e.target).get("k")); };
    el.querySelector("#sg-del")?.addEventListener("click", () => set(""));
  }
  gs.addSettingsTab({ id: "steamgriddb", label: "SteamGridDB", render: draw });
}
