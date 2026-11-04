/*
 * The popup of a contract payment: the "View details" button of a row loads
 * the contracts behind it from the server (HTML) into one Bootstrap modal.
 * A failed request shows the modal's error text; the page keeps working.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const modalElement = document.querySelector("[data-eos-spy-network-contracts-modal]");
    if (!modalElement) {
        return;
    }
    const body = modalElement.querySelector("[data-eos-spy-network-contracts-body]");
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-eos-spy-network-contracts]");
        if (!button) {
            return;
        }
        body.textContent = body.dataset.loading;
        modal.show();
        fetch(button.dataset.eosSpyNetworkContracts, { credentials: "same-origin" })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(response.status);
                }
                return response.text();
            })
            // our own server's template, which escapes everything it prints
            .then((html) => {
                body.innerHTML = html;
            })
            .catch(() => {
                body.textContent = body.dataset.failed;
            });
    });
});
