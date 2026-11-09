/*
 * The note and the cleared tick of a blue kill row (one main, one killmail):
 * the tick is a checkbox in the row, the note is edited in one popup the
 * row buttons share (as eos-tax's GM transaction notes).
 *
 * Clearing needs a note: ticking a row without one opens the popup with the
 * tick set, and Save stays off until there is a note. A row with a note is
 * ticked and unticked at once. In the settings tabs (the popup marked admin)
 * every row is ticked at once, a note or not.
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
    // set by ticking a row without a note: the popup opens with the tick already set
    let tickOnOpen = false;
    // the server takes a cleared finding without a note from an admin only
    const admin = "eosSpyNetworkKillAdmin" in modal.dataset;

    const showCount = () => {
        count.textContent = String(textarea.value.length);
        save.disabled = !admin && cleared.checked && textarea.value.trim() === "";
    };
    textarea.addEventListener("input", showCount);
    cleared.addEventListener("change", showCount);

    // Bootstrap names the button that opened the popup
    modal.addEventListener("show.bs.modal", (event) => {
        button = event.relatedTarget;
        modal.querySelector("[data-eos-spy-network-kill-note-name]").textContent = button.dataset.eosSpyNetworkKillName;
        textarea.value = button.dataset.eosSpyNetworkKillNote;
        cleared.checked = tickOnOpen || button.dataset.eosSpyNetworkKillCleared === "1";
        tickOnOpen = false;
        error.textContent = "";
        showCount();
    });

    modal.addEventListener("shown.bs.modal", () => {
        textarea.focus();
    });

    const updateRow = (target, data) => {
        const row = target.closest("tr");
        const tick = row.querySelector("[data-eos-spy-network-kill-tick]");
        target.dataset.eosSpyNetworkKillNote = data.note;
        target.dataset.eosSpyNetworkKillCleared = data.cleared ? "1" : "0";
        target.title = data.note || modal.dataset.eosSpyNetworkKillEmpty;
        row.querySelector("[data-eos-spy-network-kill-note-text]").textContent = data.note;
        tick.checked = data.cleared;
        tick.closest("td").dataset.order = data.cleared ? "1" : "0";
        row.classList.toggle("opacity-50", data.cleared);

        const table = row.closest("table");
        if (table && DataTable.isDataTable(table)) {
            // retrieve: the instance tables.js made; no draw, so the row stays where the reader is looking
            new DataTable(table, { retrieve: true }).row(row).invalidate("dom");
        }
    };

    const store = (target, note, isCleared) => {
        const body = new URLSearchParams();
        // a finding of another marker names its main and key; a blue kill its character and killmail
        const finding = "eosSpyNetworkKillKey" in target.dataset;
        if (finding) {
            body.set("kind", target.dataset.eosSpyNetworkKillKind);
            body.set("main_id", target.dataset.eosSpyNetworkKillMain);
            body.set("key", target.dataset.eosSpyNetworkKillKey);
        } else {
            body.set("character_id", target.dataset.eosSpyNetworkKillCharacter);
            body.set("killmail_id", target.dataset.eosSpyNetworkKillKillmail);
        }
        body.set("note", note);
        if (isCleared) {
            body.set("cleared", "1");
        }
        return fetch(finding ? modal.dataset.eosSpyNetworkFindingUrl : modal.dataset.eosSpyNetworkKillUrl, {
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
                updateRow(target, data);
            });
    };

    save.addEventListener("click", () => {
        save.disabled = true;
        error.textContent = "";
        store(button, textarea.value, cleared.checked)
            .then(() => {
                bootstrap.Modal.getInstance(modal).hide();
            })
            .catch((failure) => {
                error.textContent = modal.dataset.eosSpyNetworkKillError;
                console.error("eos_spy_network: saving the note failed", failure);
            })
            .finally(showCount);
    });

    document.addEventListener("change", (event) => {
        const tick = event.target.closest("[data-eos-spy-network-kill-tick]");
        if (!tick) {
            return;
        }
        const target = tick.closest("tr").querySelector("[data-eos-spy-network-kill-note]");
        if (tick.checked && target.dataset.eosSpyNetworkKillNote === "" && !admin) {
            // no note yet: ask for it, the tick is set when it is saved
            tick.checked = false;
            tickOnOpen = true;
            bootstrap.Modal.getOrCreateInstance(modal).show(target);
            return;
        }
        tick.disabled = true;
        store(target, target.dataset.eosSpyNetworkKillNote, tick.checked)
            .catch((failure) => {
                tick.checked = !tick.checked;
                window.alert(modal.dataset.eosSpyNetworkKillError);
                console.error("eos_spy_network: saving the tick failed", failure);
            })
            .finally(() => {
                tick.disabled = false;
            });
    });
});
