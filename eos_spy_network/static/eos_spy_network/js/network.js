/*
 * The mains of a network page and the connection graph of the one clicked.
 *
 * Each account's card is followed in its body by the json_script of its graph:
 * {nodes: [{id, label, group, level, standing?, sources?, affiliation?}],
 *  edges: [{from, to, kind, payments?, trades?, contracts?, direction?, first?, last?}]}.
 * A line between an own character and a partner gets arrowheads from its
 * direction ("o" the own character gave, "i" it received); the others point
 * from -> to.
 * Levels are the columns left to right: main, alts, partners, their
 * Corporations, their Alliances - so a hostile Corporation shows as the
 * reason at the end of the chain; a group behind the reason is left out and
 * named in the partner's tooltip. A graph is drawn on first show only: vis
 * cannot lay out inside a hidden container.
 * The legend's buttons show and hide a kind of counterpart node (and its
 * lines) in every graph of the page; the choice lasts until a reload.
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
    const LEVEL_SEPARATION = 320;
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
        contract: colour("contract-edge"),
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

    // vis's hierarchical layout stacks a column in JSON order and its physics run reshuffles it, so lines
    // crossed into figure eights: the columns are ordered here (barycentre sweeps both ways, the order with the
    // fewest crossings wins) and each node gets a fixed point. Returns node ID -> y.
    const place = (graph) => {
        const level = new Map(graph.nodes.map((raw) => [raw.id, raw.level]));
        const columns = new Map();
        graph.nodes.forEach((raw) => {
            if (!columns.has(raw.level)) {
                columns.set(raw.level, []);
            }
            columns.get(raw.level).push(raw.id);
        });
        const levels = [...columns.keys()].sort((a, b) => a - b);
        const y = new Map();
        const stack = (ids) => ids.forEach((id, index) => y.set(id, (index - (ids.length - 1) / 2) * NODE_SPACING));
        columns.forEach(stack);

        // lines grouped by the pair of columns they join: only lines of one pair can be counted as crossing
        const spans = new Map();
        const neighbours = new Map(graph.nodes.map((raw) => [raw.id, []]));
        graph.edges.forEach(({ from, to }) => {
            const [left, right] = level.get(from) <= level.get(to) ? [from, to] : [to, from];
            const key = `${level.get(left)}-${level.get(right)}`;
            if (!spans.has(key)) {
                spans.set(key, []);
            }
            spans.get(key).push([left, right]);
            neighbours.get(left).push(right);
            neighbours.get(right).push(left);
        });
        const crossings = () => {
            let count = 0;
            spans.forEach((pairs) => {
                pairs.forEach(([a, b], index) => {
                    pairs.slice(index + 1).forEach(([c, d]) => {
                        if ((y.get(a) - y.get(c)) * (y.get(b) - y.get(d)) < 0) {
                            count += 1;
                        }
                    });
                });
            });
            return count;
        };

        let best = new Map(y);
        let fewest = crossings();
        for (let sweep = 0; sweep < 8 && fewest; sweep += 1) {
            const leftward = sweep % 2 === 1;
            (leftward ? [...levels].reverse() : levels).forEach((at) => {
                // the mean height of the neighbours in the columns already placed this sweep; none: stay put
                const centre = (id) => {
                    const side = neighbours.get(id).filter((other) => (leftward ? level.get(other) > at : level.get(other) < at));
                    return side.length ? side.reduce((sum, other) => sum + y.get(other), 0) / side.length : y.get(id);
                };
                const ids = columns.get(at);
                const centres = new Map(ids.map((id) => [id, centre(id)]));
                ids.sort((a, b) => centres.get(a) - centres.get(b));
                stack(ids);
            });
            const count = crossings();
            if (count < fewest) {
                fewest = count;
                best = new Map(y);
            }
        }
        return best;
    };

    const period = (first, last) => (first === last ? first : `${first} – ${last}`);

    const edge = (raw) => {
        const shown = { from: raw.from, to: raw.to, color: { color: edgeColours[raw.kind] } };
        if (raw.kind === "payment" || raw.kind === "trading" || raw.kind === "contract") {
            // a contract line is labelled with its contracts, the others with their payments
            const count = raw.kind === "contract" ? raw.contracts : raw.payments;
            shown.label = String(count);
            shown.width = raw.trades ? 3 : 1 + Math.min(count, 5) / 2;
            shown.title = `${text("payments", "Payments")}: ${raw.payments} · ${text("trades", "Player trading")}: ${raw.trades}`;
            if (raw.contracts) {
                shown.title += ` · ${text("contracts", "Private contract")}: ${raw.contracts}`;
            }
            if (raw.first) {
                shown.title += `\n${text("period", "Period")}: ${period(raw.first, raw.last)}`;
            }
            // the arrow follows the giver: "o" went from the own character, "i" came to it; an older snapshot has none
            const direction = raw.direction || "";
            shown.arrows = { to: direction.includes("o"), from: direction.includes("i") };
        } else {
            // account and membership lines carry no ISK: thin and dashed, pointing to the alt / the group
            shown.dashes = true;
            shown.width = 1;
            shown.arrows = { to: true };
        }
        return shown;
    };

    // Node groups switched off in the legend, shared by every account's graph and gone with the page.
    // A hidden node keeps its place (no new layout) and takes its lines with it; the other
    // end of a line stays, so a Corporation without its partner is left standing.
    const hiddenGroups = new Set();
    const drawn = [];
    const toggles = document.querySelectorAll("[data-eos-spy-network-toggle]");
    const resets = document.querySelectorAll("[data-eos-spy-network-reset]");

    const apply = ({ nodes, edges }) => {
        const gone = (id) => hiddenGroups.has(nodes.get(id).group);
        nodes.update(nodes.get().map((raw) => ({ id: raw.id, hidden: hiddenGroups.has(raw.group) })));
        edges.update(edges.get().map((raw) => ({ id: raw.id, hidden: gone(raw.from) || gone(raw.to) })));
    };

    const refresh = () => {
        toggles.forEach((toggle) => {
            const off = hiddenGroups.has(toggle.dataset.eosSpyNetworkToggle);
            toggle.setAttribute("aria-pressed", String(!off));
            toggle.classList.toggle("opacity-50", off);
            toggle.classList.toggle("text-decoration-line-through", off);
        });
        resets.forEach((reset) => reset.classList.toggle("d-none", !hiddenGroups.size));
        drawn.forEach(apply);
    };

    toggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const group = toggle.dataset.eosSpyNetworkToggle;
            if (!hiddenGroups.delete(group)) {
                hiddenGroups.add(group);
            }
            refresh();
        });
    });
    resets.forEach((reset) => {
        reset.addEventListener("click", () => {
            hiddenGroups.clear();
            refresh();
        });
    });

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
                // every node has its fixed point from ``place``
                physics: false,
                interaction: { hover: true },
            },
        );
        const heights = place(graph);
        const nodes = new vis.DataSet(
            graph.nodes.map((raw) => ({ ...node(raw), x: raw.level * LEVEL_SEPARATION, y: heights.get(raw.id) })),
        );
        const edges = new vis.DataSet(graph.edges.map(edge));
        network.setData({ nodes: nodes, edges: edges });
        network.fit();
        drawn.push({ nodes: nodes, edges: edges });
        // a legend choice made before this card was first shown applies to it too
        apply(drawn[drawn.length - 1]);
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
