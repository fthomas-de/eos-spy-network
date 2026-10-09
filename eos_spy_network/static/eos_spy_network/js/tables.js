/*
 * Sortable tables: every table marked eos-spy-network-sortable.
 *
 * Pages of 100 rows by default, the size changeable above the table. A table
 * no longer than the smallest page size gets no paging at all: its controls
 * would only take room. A search box only above long lists. Cells sort by
 * their data-order where they have one. Every column is left-aligned:
 * DataTables puts a column with numeric data-order to the right.
 *
 * A table inside a form (eos-spy-network-form-table) gets a search box but
 * never pages: DataTables takes the rows of other pages out of the page,
 * and their checkboxes would not be sent. The search is cleared before the
 * form is sent, for the same reason.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const PAGE_LENGTHS = [25, 50, 100, 250, 500];
    const PAGE_LENGTH = 100;

    // Alliance Auth's DataTables translation for the viewer's language, set
    // by base.html; empty for English, where DataTables needs none
    const holder = document.querySelector("[data-eos-spy-network-datatables-language]");
    const languageUrl = holder ? holder.dataset.eosSpyNetworkDatatablesLanguage : "";

    document.querySelectorAll("table.eos-spy-network-sortable").forEach((table) => {
        const rows = table.tBodies[0].rows.length;
        const inForm = table.classList.contains("eos-spy-network-form-table");
        const paging = !inForm && rows > PAGE_LENGTHS[0];
        const dataTable = new DataTable(table, {
            ...(languageUrl ? { language: { url: languageUrl } } : {}),
            paging: paging,
            pageLength: PAGE_LENGTH,
            lengthMenu: PAGE_LENGTHS,
            searching: rows > 10,
            // "1 to 100 of 340" tells a reader there is more than this page
            info: paging,
            autoWidth: false,
            // keep the server's order until a header is clicked
            order: [],
            columnDefs: [
                { targets: "eos-spy-network-no-sort", orderable: false },
                { targets: "_all", className: "dt-left" },
            ],
        });

        const form = table.closest("form");
        if (inForm && form) {
            form.addEventListener("submit", () => {
                // client-side drawing is synchronous: every row is back before the form is read
                dataTable.search("").draw();
            });
        }
    });
});
