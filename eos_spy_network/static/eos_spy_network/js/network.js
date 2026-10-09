/*
 * The mains of a network page and the connection graph of the one clicked.
 *
 * Each account's card is followed in its body by the json_script of its graph:
 * {nodes: [{id, label, group, level, standing?, sources?, affiliation?}],
 *  edges: [{from, to, kind, payments?, trades?, first?, last?}]}.
 * Levels are the columns left to right: main, alts, partners, their
 * Corporations, their Alliances - so a hostile Corporation shows as the
 * reason at the end of the chain; a group behind the reason is left out and
 * named in the partner's tooltip. A graph is drawn on first show only: vis
 * cannot lay out inside a hidden container.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    const buttons = document.querySelectorAll("[data-eos-spy-network-show]");
    if (!buttons.length) {
        return;
    }
    const placeholder = document.querySelector("[data-eos-spy-network-placeholder]");
    const labels = document.querySelector("[data-eos-spy-network-graph-labels]");
    const text = (name, fallback) => (labels && labels.dataset[name]) || fallback;

    const colour = (name) => {
        const icon = document.querySelector(`.eos-spy-network-legend-${name}`);
        return icon ? getComputedStyle(icon).color : "#888888";
    };
    const textColour = getComputedStyle(document.body).color;
    const NODE_SPACING = 110;
    const SHAPES = {
        main: ["dot", 20],
        alt: ["dot", 14],
        partner: ["diamond", 14],
        hostile_partner: ["diamond", 14],
        corporation: ["square", 13],
        hostile_corporation: ["square", 15],
        alliance: ["hexagon", 15],
        hostile_alliance: ["hexagon", 17],
    };
    const groups = {};
    Object.entries(SHAPES).forEach(([name, [shape, size]]) => {
        groups[name] = {
            color: { background: colour(name), border: colour(name) },
            shape: shape,
            size: size,
        };
    });
    const edgeColours = {
        payment: colour("payment-edge"),
        trading: colour("trading-edge"),
        account: colour("alt"),
        member: colour("corporation"),
    };

    const node = (raw) => {
        const shown = { ...raw };
        const lines = [...(raw.affiliation || [])];
        if (raw.standing !== undefined) {
            // the reason in the label itself, the sources in the tooltip
            shown.label = `${raw.label}\n${text("standing", "Standing")} ${raw.standing}`;
            lines.push(...raw.sources.map(([source, standing]) => `${source}: ${standing}`));
        }
        if (lines.length) {
            shown.title = lines.join("\n");
        }
        return shown;
    };

    const period = (first, last) => (first === last ? first : `${first} – ${last}`);

    const edge = (raw) => {
        const shown = { from: raw.from, to: raw.to, color: { color: edgeColours[raw.kind] } };
        if (raw.kind === "payment" || raw.kind === "trading") {
            // the count stays in the tooltip: labels on a bundle of lines cover each other
            shown.width = raw.trades ? 3 : 1 + Math.min(raw.payments, 5) / 2;
            shown.title = `${text("payments", "Payments")}: ${raw.payments} · ${text("trades", "Player trading")}: ${raw.trades}`;
            if (raw.first) {
                shown.title += `\n${text("period", "Period")}: ${period(raw.first, raw.last)}`;
            }
        } else {
            // account and membership lines carry no ISK: thin and dashed
            shown.dashes = true;
            shown.width = 1;
        }
        return shown;
    };

    const draw = (card) => {
        if (card.dataset.drawn || typeof vis === "undefined") {
            return;
        }
        const container = card.querySelector("[data-eos-spy-network-graph]");
        const script = container && container.nextElementSibling;
        if (!script || script.type !== "application/json") {
            return;
        }
        const graph = JSON.parse(script.textContent);
        // the fullest column decides the height: a fixed one squeezes many partners on top of each other
        const perLevel = {};
        graph.nodes.forEach((raw) => {
            perLevel[raw.level] = (perLevel[raw.level] || 0) + 1;
        });
        const fullest = Math.max(1, ...Object.values(perLevel));
        container.style.height = `${Math.min(1600, Math.max(420, fullest * NODE_SPACING + 120))}px`;
        // created empty: with the data in the constructor the stabilization ends before a listener exists
        const network = new vis.Network(
            container,
            {},
            {
                groups: groups,
                // long names wrap instead of reaching into the next column
                nodes: { font: { color: textColour }, widthConstraint: { maximum: 220 } },
                edges: {
                    font: { color: textColour, strokeWidth: 0, align: "middle" },
                    smooth: { type: "cubicBezier", forceDirection: "horizontal", roundness: 0.4 },
                },
                layout: {
                    hierarchical: {
                        direction: "LR",
                        levelSeparation: 320,
                        nodeSpacing: NODE_SPACING,
                        treeSpacing: NODE_SPACING * 1.5,
                        blockShifting: true,
                        edgeMinimization: true,
                        parentCentralization: true,
                        sortMethod: "directed",
                        shakeTowards: "roots",
                    },
                },
                // the layout alone stacks two-line labels into each other; a short repulsion
                // run pushes them apart within their column, then the graph stands still
                physics: {
                    hierarchicalRepulsion: { nodeDistance: NODE_SPACING, avoidOverlap: 1 },
                    stabilization: { iterations: 300, fit: true },
                },
                interaction: { hover: true },
            },
        );
        network.once("stabilizationIterationsDone", () => {
            network.setOptions({ physics: false });
            network.fit();
        });
        network.setData({
            nodes: new vis.DataSet(graph.nodes.map(node)),
            edges: new vis.DataSet(graph.edges.map(edge)),
        });
        card.dataset.drawn = "1";
    };

    const show = (mainId) => {
        let found = false;
        document.querySelectorAll("[data-eos-spy-network-account]").forEach((card) => {
            const match = card.dataset.eosSpyNetworkAccount === mainId;
            card.classList.toggle("d-none", !match);
            if (match) {
                found = true;
                draw(card);
                // DataTables measured the columns while the card was hidden
                if (typeof DataTable !== "undefined") {
                    DataTable.tables({ visible: true, api: true }).columns.adjust();
                }
            }
        });
        buttons.forEach((button) => {
            button.classList.toggle("active", button.dataset.eosSpyNetworkShow === mainId);
        });
        if (placeholder) {
            placeholder.classList.toggle("d-none", found);
        }
        return found;
    };

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const mainId = button.dataset.eosSpyNetworkShow;
            show(mainId);
            // a link to the page opens the same main again
            history.replaceState(null, "", `#main-${mainId}`);
        });
    });

    const fromHash = window.location.hash.match(/^#main-(\d+)$/);
    if (fromHash) {
        show(fromHash[1]);
    }
});
