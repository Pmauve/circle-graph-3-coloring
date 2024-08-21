const ImportantSubgraphIds = {
    Tailtriangle: 'TT',
    Boxsquare: 'BSq',
    Square: 'Sq',
    Pentagram: 'Pent',
    BigCycle: 'Cyc'
}

// set the dimensions and margins of the graph
var margin = {top: 50, right: 30, bottom: 20, left: 30},
    width = 1600 - margin.left - margin.right,
    height = 800 - margin.top - margin.bottom;

var marginCountTT = 0;
var marginCountBSq = 0;
var marginCountSq = 0;
var marginCountPent = 0;
var marginCountCyc = 0;

// append the svg object to the body of the page
var svg = null

var inputPath = "../";
var fileName = "/broken_counter_test_graph.json"

let graph = getGraphFromJSON(inputPath + fileName)
drawGraph(graph)

var input = document.getElementById("file_name")
input.addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        refresh()
    }
})

function refresh() {
    fileName = input.value;
    d3.select("#my_dataviz").selectAll("*").remove();
    console.log(inputPath + fileName)
    drawGraph(getGraphFromJSON(inputPath + fileName + ".json"));
}

function getGraphFromJSON(path) {
    var request = new XMLHttpRequest();
    request.open("GET", path, false);
    request.send(null);
    var graphFromJSON = JSON.parse(request.responseText);
    let nodes = graphFromJSON.nodes;
    let links = graphFromJSON.links;
    return {nodes, links};
}

function drawGraph(data) {
    function findVertexByIndex(d) {
        return data.nodes.find(function (n) {
            if (n.l === d || n.r === d) {
                return n;
            }
        })
    }

    function isNeighbor(v, link_d) {
        return (link_d.l < v.l && v.l < link_d.r && link_d.r < v.r) || //crosses left endpoint
            (v.l < link_d.l && link_d.l < v.r && v.r < link_d.r) // crosses right endpoint
    }

    width = Math.max(1000, (data.nodes.length * 60) - margin.left - margin.right);
    // height = Math.max(1000, (width * 0.2) - margin.top - margin.bottom);
    svg = d3.select("#my_dataviz")
        .append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform",
            "translate(" + margin.left + "," + margin.top + ")");

    var leftEndpoints = data.nodes.map(function (d) {
        return d.l;
    })
    var rightEndpoints = data.nodes.map(function (d) {
        return d.r;
    })
    var allNodes = leftEndpoints.concat(rightEndpoints);
    allNodes.sort(function (a, b) {
        return a - b;
    })
    // A linear scale to position the nodes on the X axis
    var x = d3.scalePoint()
        .range([0, width - 80])
        .domain(allNodes)
    // Add the circle for the nodes
    var nodes = svg
        .selectAll("mynodes")
        .data(allNodes)
        .enter()
        .append("circle")
        .attr("cx", function (d) {
            return (x(d))
        })
        .attr("cy", height * 0.7)
        .attr("r", 8)
        .style("fill", function (d) {
            var v = findVertexByIndex(d)
            return getColorForVertex(v);
        })

    // And give them a label
    var left_labels = svg
        .selectAll("myleftlabels")
        .data(data.nodes)
        .enter()
        .append("text")
        .attr("x", function (d) {
            return (x(d.l))
        })
        .attr("y", (height * 0.7) + 20)
        .text(function (d) {
            return (d.id)
        })
        .style("text-anchor", "middle")
    var right_labels = svg
        .selectAll("myrightlabels")
        .data(data.nodes)
        .enter()
        .append("text")
        .attr("x", function (d) {
            return (x(d.r))
        })
        .attr("y", (height * 0.7) + 20)
        .text(function (d) {
            return (d.id)
        })
        .style("text-anchor", "middle")

    // Add links between nodes. Here is the tricky part.
    // In my input data, links are provided between nodes -id-, NOT between node names.
    // So I have to do a link between this id and the name
    var idToNode = {};
    data.nodes.forEach(function (n) {
        idToNode[n.id] = n;
    });
    // Cool, now if I do idToNode["2"].name I've got the name of the node with id 2

    // Add the links
    var links = svg
        .selectAll('mylinks')
        .data(data.nodes)
        .enter()
        .append('path')
        .attr('d', function (d) {
            start = x(d.l)    // X position of start node on the X axis
            end = x(d.r)      // X position of end node
            control = (end - start) / 2;
            return ['M', start, height * 0.7,    // the arc starts at the coordinate x, y (where the starting node is)
                'C',                            // This means we're building a quadratic Bézier curve
                start, (height * 0.7) - 10 - control,
                end, (height * 0.7) - 10 - control,
                end, height * 0.7] // We always want the arc on top. So if end is before start, putting 0 here turn the arc upside down.
                .join(' ');
        })
        .style("fill", "none")
        .attr("stroke", function (l) {
            return getColorForVertex(l);
        })

    var levelLabelsLeft = svg
        .selectAll("levellabels")
        .data(data.nodes)
        .enter()
        .append("text")
        .attr("x", function (d) {
            return (x(d.l) - 2)
        })
        .attr("y", function (d) {
            return (height * 0.7) - 12
        })
        .text(function (d) {
            if (d.level > -1) {
                return (d.level)
            } else {
                return ""
            }
        })
        .style("text-anchor", "middle")

    var levelLabelsRight = svg
        .selectAll("levellabels")
        .data(data.nodes)
        .enter()
        .append("text")
        .attr("x", function (d) {
            return (x(d.r) + 2)
        })
        .attr("y", function (d) {
            return (height * 0.7) - 12
        })
        .text(function (d) {
            if (d.level > -1) {
                return (d.level)
            } else {
                return ""
            }
        })
        .style("text-anchor", "middle")

    const importantSubgraphs = svg
        .append("text")
        .attr("text-anchor", "left")
        .style("visibility", "hidden");


    // Add the highlighting functionality
    nodes
        .on('mouseover', function (d) {
            var node_d = findVertexByIndex(d);
            // Highlight the nodes: every node is green except of him
            nodes.style('fill', function (n) {
                var node_n = findVertexByIndex(n)
                if (node_d.id === node_n.id) {
                    return '#69b3b2';
                } else if (isNeighbor(node_d, node_n)) {
                    return '#888888'
                } else {
                    return '#b8b8b8';
                }
            })
            // Highlight the connections
            links
                .style('stroke', function (link_d) {
                    if (link_d.l === d || link_d.r === d) {
                        return '#69b3b2';
                    } else if (isNeighbor(node_d, link_d)) {
                        return '#888888';
                    } else {
                        return '#b8b8b8';
                    }
                })
                .style('stroke-width', function (link_d) {
                    if (link_d.id === node_d.id) {
                        return 4;
                    } else if (isNeighbor(node_d, link_d)) {
                        return 2;
                    } else {
                        return 1;
                    }
                })
            importantSubgraphs
                .style("visibility", null)

            var subgraphs = node_d.importantsubgraphs;
            if (subgraphs.length > 0) {
                subgraphs.forEach(function (s) {
                    importantSubgraphs
                        .append("tspan")
                        .attr("class", "nodes")
                        .attr("x", Math.max(x(d), width - 900) + getOffset(s.id))
                        .attr("y", (height * 0.7) + 50 + getMargin(s.id))
                        .text(s.id + ": " + s.nodes);
                })
            }
        })
        .on('mouseout', function () {
            nodes.style('fill', function (n) {
                var v = findVertexByIndex(n)
                return getColorForVertex(v);
            })
            links
                .style('stroke', function (l) {
                    return getColorForVertex(l);
                })
                .style('stroke-width', '1')
            importantSubgraphs
                .style("visibility", "hidden");
            svg.selectAll(".nodes").remove();
            marginCountTT = 0;
            marginCountBSq = 0;
            marginCountSq = 0;
            marginCountPent = 0;
            marginCountCyc = 0;
        })
}

// Read dummy data
d3.json(inputPath, function (data) {

})

// text hover nodes
svg
    .append("text")
    .attr("text-anchor", "middle")
    .style("fill", "#B8B8B8")
    .style("font-size", "17px")
    .attr("x", 50)
    .attr("y", 10)
    .html("")

function getOffset(string) {
    if (string.startsWith(ImportantSubgraphIds.Tailtriangle)) {
        return 0;
    } else if (string.startsWith(ImportantSubgraphIds.Boxsquare)) {
        return 150;
    } else if (string.startsWith(ImportantSubgraphIds.Square)) {
        return 300;
    } else if (string.startsWith(ImportantSubgraphIds.Pentagram)) {
        return 450;
    } else if (string.startsWith(ImportantSubgraphIds.BigCycle)) {
        return 600;
    }
}

function getMargin(string) {
    if (string.startsWith(ImportantSubgraphIds.Tailtriangle)) {
        marginCountTT += 25;
        return marginCountTT;
    } else if (string.startsWith(ImportantSubgraphIds.Boxsquare)) {
        marginCountBSq += 25;
        return marginCountBSq;
    } else if (string.startsWith(ImportantSubgraphIds.Square)) {
        marginCountSq += 25;
        return marginCountSq;
    } else if (string.startsWith(ImportantSubgraphIds.Pentagram)) {
        marginCountPent += 25;
        return marginCountPent;
    } else if (string.startsWith(ImportantSubgraphIds.BigCycle)) {
        marginCountCyc += 25;
        return marginCountCyc;
    }
}

function getColorForVertex(v) {
    if (v.color === 0 || v.color === 3) {
        return "#36aceb";
    } else if (v.color === 1) {
        return "#e75858";
    } else if (v.color === 2) {
        return "#8ec48b";
    }
    return "#5d5d5d"
}