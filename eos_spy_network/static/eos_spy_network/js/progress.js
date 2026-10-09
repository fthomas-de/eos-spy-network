/*
 * The progress bar of a running recalculation.
 *
 * Polls the progress URL and moves the bar; once the task is done the page
 * reloads, so it shows the new result. A failed poll (network, server
 * restart) only skips that round.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const box = document.querySelector("[data-eos-spy-network-progress]");
    if (!box) {
        return;
    }
    const url = box.dataset.eosSpyNetworkProgress;
    const label = box.querySelector("[data-eos-spy-network-progress-label]");
    const track = box.querySelector("[data-eos-spy-network-progress-track]");
    const bar = box.querySelector("[data-eos-spy-network-progress-bar]");
    const INTERVAL = 2000;

    const poll = () => {
        fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
            .then((response) => (response.ok ? response.json() : null))
            .then((state) => {
                if (!state) {
                    window.setTimeout(poll, INTERVAL);
                    return;
                }
                if (!state.running) {
                    window.location.reload();
                    return;
                }
                label.textContent = state.label;
                bar.style.width = `${state.percent}%`;
                bar.textContent = `${state.percent} %`;
                track.setAttribute("aria-valuenow", state.percent);
                window.setTimeout(poll, INTERVAL);
            })
            .catch(() => window.setTimeout(poll, INTERVAL));
    };
    window.setTimeout(poll, INTERVAL);
});
