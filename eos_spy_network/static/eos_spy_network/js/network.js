/*
 * The connection graph of each account on a network page.
 *
 * Every graph container is followed by the json_script of its account:
 * {nodes: [{id, label, group}], edges: [{from, to, payments, trades}]}.
 * The colours come from the legend icons, which take them from the theme.
 */
document.addEventListener("DOMContentLoaded", () => {
    "use strict";

    if (typeof vis === "undefined") {
        return;
    }

    const labels = document.querySelector("[data-eos-spy-network-graph-labels]");
    const colour = (name) => {
        const icon = document.querySelector(`.eos-spy-network-legend-${name}`);
        return icon ? getComputedStyle(icon).color : "#888888";
    };
    const textColour = getComputedStyle(document.body).color;
    const groups = {};
    ["main", "alt", "shared", "trading"].forEach((name) => {
        groups[name] = {
            color: { background: colour(name), border: colour(name) },
            shape: name === "main" || name === "alt" ? "dot" : "diamond",
            size: name === "main" ? 18 : 12,
        };
    });
    const paymentEdge = colour("payment-edge");
    const tradingEdge = colour("trading-edge");

    document.querySelectorAll("[data-eos-spy-network-graph]").forEach((container) => {
        const script = container.nextElementSibling;
        if (!script || script.type !== "application/json") {
            return;
        }
        const graph = JSON.parse(script.textContent);
        const edges = graph.edges.map((edge) => ({
            from: edge.from,
            to: edge.to,
            label: String(edge.payments),
            // a trade window deal is the closer contact: it decides the colour
            color: { color: edge.trades ? tradingEdge : paymentEdge },
            width: edge.trades ? 3 : 1 + Math.min(edge.payments, 5) / 2,
            title: `${labels ? labels.dataset.payments : "Payments"}: ${edge.payments} · ${labels ? labels.dataset.trades : "Player trading"}: ${edge.trades}`,
        }));
        new vis.Network(
            container,
            { nodes: new vis.DataSet(graph.nodes), edges: new vis.DataSet(edges) },
            {
                groups: groups,
                nodes: { font: { color: textColour } },
                edges: { font: { color: textColour, strokeWidth: 0, align: "middle" }, smooth: false },
                physics: { stabilization: { iterations: 200 } },
                interaction: { hover: true },
            },
        );
    });
});
