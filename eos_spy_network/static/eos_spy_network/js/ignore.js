/*
 * The "ignore this counterpart" popup of the Network page: the button of a
 * row hands its counterpart's ID and name to the one confirmation modal.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const modal = document.getElementById("eos-spy-network-ignore");
    if (!modal) {
        return;
    }
    modal.addEventListener("show.bs.modal", (event) => {
        const button = event.relatedTarget;
        modal.querySelector("[data-eos-spy-network-ignore-field]").value = button.dataset.eosSpyNetworkIgnoreId;
        // textContent: the name is a player's text
        modal.querySelector("[data-eos-spy-network-ignore-name]").textContent = button.dataset.eosSpyNetworkIgnoreName;
    });
});
