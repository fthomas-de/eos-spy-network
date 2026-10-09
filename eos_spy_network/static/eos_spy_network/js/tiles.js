/*
 * The switch above the marker tiles: hides the Corporations without markers.
 *
 * The choice is kept per browser; storage may be blocked (private window,
 * cleared site data), so every access is guarded and the page works without.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const KEY = "eos-spy-network-hide-clean";
    const toggle = document.querySelector("[data-eos-spy-network-hide-clean]");
    if (!toggle) {
        return;
    }

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
