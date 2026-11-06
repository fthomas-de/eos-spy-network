/*
 * The note and the cleared tick of a blue kill row, edited in one popup the
 * row buttons share (as eos-tax's GM transaction notes).
 *
 * A note is someone's free text, so it only ever travels as text: read from
 * value and dataset, written to value, textContent and attributes - never as
 * markup. The page shows what the server stored, not what was typed.
 *
 * On the Corporation page the marker's count depends on the tick, so the
 * page reloads after a save; in the settings tab the row is updated in place
 * and DataTables told, so sorting and the search see the new note.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const modal = document.getElementById("eos-spy-network-kill-note");
    if (!modal) {
        return;
    }
    const textarea = modal.querySelector("textarea");
    const cleared = modal.querySelector("input[type=checkbox]");
    const count = modal.querySelector("[data-eos-spy-network-kill-note-count]");
    const error = modal.querySelector("[data-eos-spy-network-kill-note-error]");
    const save = modal.querySelector("[data-eos-spy-network-kill-note-save]");
    let button = null;

    // a kill is cleared only with a note saying why; the server refuses it otherwise
    const showCount = () => {
        count.textContent = String(textarea.value.length);
        const hasNote = textarea.value.trim() !== "";
        cleared.disabled = !hasNote;
        if (!hasNote) {
            cleared.checked = false;
        }
    };
    textarea.addEventListener("input", showCount);

    // Bootstrap names the button that opened the popup
    modal.addEventListener("show.bs.modal", (event) => {
        button = event.relatedTarget;
        modal.querySelector("[data-eos-spy-network-kill-note-name]").textContent = button.dataset.eosSpyNetworkKillName;
        textarea.value = button.dataset.eosSpyNetworkKillNote;
        cleared.checked = button.dataset.eosSpyNetworkKillCleared === "1";
        error.textContent = "";
        showCount();
    });

    modal.addEventListener("shown.bs.modal", () => {
        textarea.focus();
    });

    const updateRow = (data) => {
        const cell = button.closest("td");
        const row = cell.closest("tr");
        button.dataset.eosSpyNetworkKillNote = data.note;
        button.dataset.eosSpyNetworkKillCleared = data.cleared ? "1" : "0";
        button.title = data.note || modal.dataset.eosSpyNetworkKillEmpty;
        button.classList.toggle("btn-secondary", Boolean(data.note || data.cleared));
        button.classList.toggle("btn-outline-secondary", !(data.note || data.cleared));
        cell.querySelector("[data-eos-spy-network-kill-note-text]").textContent = data.note;
        cell.querySelector("[data-eos-spy-network-kill-cleared-badge]").classList.toggle("d-none", !data.cleared);
        row.classList.toggle("opacity-50", data.cleared);

        const clearedCell = row.querySelector("[data-eos-spy-network-kill-cleared-cell]");
        if (clearedCell) {
            clearedCell.dataset.order = data.cleared ? "1" : "0";
        }
        const table = row.closest("table");
        if (table && DataTable.isDataTable(table)) {
            // retrieve: the instance tables.js made; no draw, so the row stays where the reader is looking
            new DataTable(table, { retrieve: true }).row(row).invalidate("dom");
        }
    };

    save.addEventListener("click", () => {
        const body = new URLSearchParams();
        body.set("character_id", button.dataset.eosSpyNetworkKillCharacter);
        body.set("killmail_id", button.dataset.eosSpyNetworkKillKillmail);
        body.set("note", textarea.value);
        if (cleared.checked) {
            body.set("cleared", "1");
        }
        save.disabled = true;
        error.textContent = "";

        fetch(modal.dataset.eosSpyNetworkKillUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": modal.querySelector("[name=csrfmiddlewaretoken]").value,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: body.toString(),
        })
            .then((response) => {
                if (!response.ok) {
                    throw new Error(response.status);
                }
                return response.json();
            })
            .then((data) => {
                if ("eosSpyNetworkKillReload" in modal.dataset) {
                    window.location.reload();
                    return;
                }
                updateRow(data);
                bootstrap.Modal.getInstance(modal).hide();
            })
            .catch((failure) => {
                error.textContent = modal.dataset.eosSpyNetworkKillError;
                console.error("eos_spy_network: saving the note failed", failure);
            })
            .finally(() => {
                save.disabled = false;
            });
    });
});
