/*
 * The switch above the tiles: hides the Corporations without findings -
 * without markers on the Markers page, without connections on the Network page.
 *
 * The switch's value names the page, so each page remembers its own choice.
 * The choice is kept per browser; storage may be blocked (private window,
 * cleared site data), so every access is guarded and the page works without.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const toggle = document.querySelector("[data-eos-spy-network-hide-clean]");
    if (!toggle) {
        return;
    }
    const page = toggle.dataset.eosSpyNetworkHideClean;
    // the Markers page had the switch first; its key stays, or every viewer loses the choice
    const KEY = page ? `eos-spy-network-hide-clean-${page}` : "eos-spy-network-hide-clean";

    const apply = () => {
        document.querySelectorAll("[data-eos-spy-network-clean]").forEach((tile) => {
            tile.classList.toggle("d-none", toggle.checked);
        });
    };

    try {
        toggle.checked = window.localStorage.getItem(KEY) === "1";
    } catch (error) {
        toggle.checked = false;
    }
    apply();

    toggle.addEventListener("change", () => {
        apply();
        try {
            window.localStorage.setItem(KEY, toggle.checked ? "1" : "0");
        } catch (error) {
            // not remembered; the switch still works for this page
        }
    });
});
