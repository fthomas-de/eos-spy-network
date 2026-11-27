/*
 * The info button of a summed ISK, contracts or mails case: a popover with
 * every journal entry, contract or mail of the case, its table taken from the <template>
 * after the button (user, 2026-11-27). items.css lets a long list scroll.
 *
 * Made on the first click, not at load: DataTables draws the rows of other
 * pages later. The focus trigger closes it on the next click elsewhere.
 */
document.addEventListener("click", (event) => {
    "use strict";

    const button = event.target.closest("[data-eos-spy-network-items]");
    if (!button || bootstrap.Popover.getInstance(button)) {
        return;
    }
    bootstrap.Popover.getOrCreateInstance(button, {
        // a node, not a string: Bootstrap appends it as it is, the server escaped its text
        content: () => button.nextElementSibling.content.firstElementChild.cloneNode(true),
        html: true,
        trigger: "focus",
        customClass: "eos-spy-network-items",
    }).show();
});
