/*
 * The cleared findings at the foot of the Corporation page: a group per main,
 * folded. The search keeps the groups whose main or rows match, unfolds them
 * and hides the rows that do not match; an empty search folds everything again.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const search = document.querySelector("[data-eos-spy-network-cleared-search]");
    if (!search) {
        return;
    }
    const groups = document.querySelectorAll("[data-eos-spy-network-cleared-group]");

    search.addEventListener("input", () => {
        const query = search.value.trim().toLowerCase();
        groups.forEach((group) => {
            const header = group.querySelector("button");
            // a hit on the main's name shows all its rows
            const mainHit = header.textContent.toLowerCase().includes(query);
            let rowHit = false;
            group.querySelectorAll("tbody tr").forEach((row) => {
                const hit = mainHit || row.textContent.toLowerCase().includes(query);
                row.classList.toggle("d-none", !hit);
                rowHit = rowHit || hit;
            });
            group.classList.toggle("d-none", !rowHit);
            const collapse = bootstrap.Collapse.getOrCreateInstance(group.querySelector(".collapse"), { toggle: false });
            if (query && rowHit) {
                collapse.show();
            } else {
                collapse.hide();
            }
        });
    });
});
