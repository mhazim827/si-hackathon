(() => {
  const esc = value => String(value || "").replace(/[&<>'"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;",'"':"&quot;"}[char]));
  const render = programs => `<section class="surface profile-wide"><div class="surface-title"><div><p class="eyebrow">My learning programmes</p><h2>Registered learning</h2></div></div>${programs.length ? `<div class="portfolio-grid">${programs.map(program => `<article class="portfolio-item"><span class="type-pill">${esc(program.format)}</span><h3>${esc(program.title)}</h3><p>${esc(program.provider)} · ${esc(program.mode)} · ${esc(program.duration)}</p><small>Registered ${new Date(program.registered_at).toLocaleDateString()}</small></article>`).join("")}</div>` : `<p class="muted">Learning programmes you register for will appear here.</p>`}</section>`;
  function addProgramSection() {
    if (window.SKILLBRIDGE_ROLE !== "student") return;
    fetch("/api/profile").then(response => response.json()).then(data => {
      const insert = () => {
        const grid = document.querySelector("#profile-content .profile-grid");
        if (!grid) return setTimeout(insert, 80);
        if (!document.querySelector("#registered-programmes-profile")) {
          const wrapper = document.createElement("div");
          wrapper.id = "registered-programmes-profile";
          wrapper.style.display = "contents";
          wrapper.innerHTML = render(data.registered_programs || []);
          grid.appendChild(wrapper);
        }
      };
      insert();
    }).catch(() => {});
  }
  document.addEventListener("DOMContentLoaded", addProgramSection);
})();
