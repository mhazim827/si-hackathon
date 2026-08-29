(() => {
  const clearButton = `<button class="btn ghost small notification-clear" data-clear-notifications>Clear all</button>`;
  function addControl() {
    const panel = document.querySelector("#notifications");
    if (!panel || panel.querySelector("[data-clear-notifications]") || !panel.querySelector(".notification")) return;
    panel.insertAdjacentHTML("afterbegin", clearButton);
  }
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-clear-notifications]");
    if (!button || !confirm("Clear all notifications for this account?")) return;
    button.disabled = true;
    fetch("/api/notifications", {method:"DELETE"}).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.message || "Could not clear notifications.");
      document.querySelector("#notifications").innerHTML = `<p class="muted">No notifications yet.</p>`;
    }).catch(error => { button.disabled = false; alert(error.message); });
  });
  document.addEventListener("DOMContentLoaded", () => {
    addControl();
    const panel = document.querySelector("#notifications");
    if (panel) new MutationObserver(addControl).observe(panel, {childList:true});
  });
})();
