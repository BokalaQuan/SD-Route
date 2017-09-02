var CONF = {
    image: {
        width: 50,
        height: 40
    },
    force: {
        width: 1000,
        height: 500,
        dist: 150,
        charge: -500
    }
};

var ws = new WebSocket("ws://" + location.host + "/v1.0/topology/ws");
ws.onmessage = function(event) {
    var data = JSON.parse(event.data);
    //console.log('websocket:'+JSON.stringify(data));

    var result = rpc[data.method](data.params);

    var ret = {"id": data.id, "jsonrpc": "2.0", "result": result};
    this.send(JSON.stringify(ret));
}

function trim_zero(obj) {
    return String(obj).replace(/^0+/, "");
}

function sixteen_to_ten(obj) {
    var tem ='0x'+obj;
    var i = parseInt(tem);
    return i
}

function dpid_to_int(dpid) {
    return Number("0x" + dpid);
}

var elem = {
    force: d3.layout.force()
        .size([CONF.force.width, CONF.force.height])
        .charge(CONF.force.charge)
        .linkDistance(CONF.force.dist)
        .on("tick", _tick),//tick 指的是时间间隔，也就是每一个时间间隔之后就刷新一遍画面，
    svg: d3.select("body")
        .append("div").attr("id","con").attr("class","container").style("padding-top",'0px')
        .append("svg")
        //.attr("id", "topology")
        .attr("width", CONF.force.width)
        .attr("height", CONF.force.height),
    console: d3.select("body").append("div")
        .attr("id", "console")
        .attr("width", CONF.force.width)
};
function _tick() {
    elem.link.attr("x1", function(d) { return d.source.x; })
        .attr("y1", function(d) { return d.source.y; })
        .attr("x2", function(d) { return d.target.x; })
        .attr("y2", function(d) { return d.target.y; });

    elem.node.attr("transform", function(d) { return "translate(" + d.x + "," + d.y + ")"; });

    elem.port.attr("transform", function(d) {
        var p = topo.get_port_point(d);
        return "translate(" + p.x + "," + p.y + ")";
    });
}
//拖拽事件
elem.drag = elem.force.drag().on("dragstart", _dragstart);
function _dragstart(d) {
    var dpid = dpid_to_int(d.dpid);
    d3.json("/stats/flow/" + dpid, function(e, data) {
        flows = data[dpid];
        console.log(JSON.stringify(flows));
        elem.console.selectAll("table").remove();
        li = elem.console
            .append("table").attr("class","table table-hover")
        li.append("caption").text("FLOW TABLES")
        //画一个bootstrap表格～
        var li_th = li.append("thead").append("tr");
        li_th.append("th").text("#");
        li_th.append("th").text("actions");
        li_th.append("th").text("duration seconds");
        li_th.append("th").text("nw_dst");
        li_th.append("th").text("nw_src");
        li_th.append("th").text("dl_dst");
        var li_tb=li.append("tbody");
        var len = flows.length;
        for(var i=0;i<len;i++)
        {
            var tr = li_tb.append("tr");
            tr.append("td").text(i+1);
            tr.append("td").text(flows[i].actions);
            tr.append("td").text(flows[i].duration_sec);
            tr.append("td").text(flows[i].match.nw_dst);
            tr.append("td").text(flows[i].match.nw_src);
            tr.append("td").text(flows[i].match.dl_dst);
        }
    });
    d3.select(this).classed("fixed", d.fixed = true);
}
elem.node = elem.svg.selectAll(".node");
elem.link = elem.svg.selectAll(".link");
elem.port = elem.svg.selectAll(".port");
elem.update = function () {
    this.force
        .nodes(topo.nodes)
        .links(topo.links)
        .start();

    this.link = this.link.data(topo.links);
    this.link.exit().remove();
    this.link.enter().append("line")
        .attr("id", function (d) {return "p" + d.source.dpid + d.target.dpid;})//每条链接加上ID
        //.attr("id_h", function (d) {return "p" + d.source.dpid + d.target.ip;})//主机与交换机的连接
        .attr("class", "link");
    var len = topo.links.length;
    var len_r_s = topo.root_set.length;
    console.log(len_r_s)
    var len_dij_event_send = topo.root_set_dij.length
    console.log(len_dij_event_send)

    for(var j=0;j<len;j++) {
        var id_l_i ="p" + topo.links[j].port.src.dpid + topo.links[j].port.dst.dpid;//链路ID;
        //console.log('124-id_l_i:'+id_l_i);
        if (len_r_s == 0) {
            d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
            console.log('len_r_s=0')
            //d3.select("#" + id_l_i).attr("style", "stroke:rgb(169,169,169)");//默认颜色
        }
        else {
            for (var i = 0; i < len_r_s; i++) {
                var id_c = "p" + topo.root_set[i].port.src.dpid + topo.root_set[i].port.dst.dpid;//需要变色的ID
                var id_c_2 = "p" + topo.root_set[i].port.dst.dpid + topo.root_set[i].port.src.dpid;//需要变色的ID
                //console.log('130-id_c:'+id_c);
                if (id_l_i == id_c || id_l_i==id_c_2) {
                    d3.select("#" + id_l_i).attr("style", "stroke:rgb(255,0,0)");
                    //d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
                    break;
                }
                else {
                    d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
                    //d3.select("#" + id_l_i).attr("style", "stroke:rgb(169,169,169)");//默认颜色
                }
            }
            for (var k=0; k < len_dij_event_send; k++){
                var id_link_change_color_dij = "p" + topo.root_set_dij[k].port.src.dpid + topo.root_set_dij[k].port.dst.dpid;
                var id_link_change_color_dij_2 = "p" + topo.root_set_dij[k].port.dst.dpid + topo.root_set_dij[k].port.src.dpid;

                if(id_l_i == id_link_change_color_dij || id_l_i==id_link_change_color_dij_2){
                    d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,255,0)");
                    //d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
                    break;
                }
            }
        }
    }


    this.node = this.node.data(topo.nodes);
    this.node.exit().remove();
    var nodeEnter = this.node.enter().append("g")
        .attr("class", "node")
        .on("dblclick", function(d) { d3.select(this).classed("fixed", d.fixed = false); })
        .call(this.drag);
    nodeEnter.append("image")
        .attr("xlink:href", function(d){
            //console.log(d.dpid);
            //  console.log(d.ipv4);
            if (d.dpid ==undefined )
                return "./image/router_red.png";
            else return"./image/router.png"})
        .attr("x", -CONF.image.width/2)
        .attr("y", -CONF.image.height/2)
        .attr("width", CONF.image.width)
        .attr("height", CONF.image.height);
    nodeEnter.append("text")
        .attr("dx", -CONF.image.width/2)
        .attr("dy", CONF.image.height-10)
        .text(function(d) {
            if (d.dpid ==undefined )
                return     "ipv4: " + trim_zero(d.ipv4);
            else return  "dpid: " + sixteen_to_ten(d.dpid)
   });


    var ports = topo.get_ports();
    this.port.remove();
    this.port = this.svg.selectAll(".port").data(ports);
    var portEnter = this.port.enter().append("g")
        .attr("class", "port");
    portEnter.append("circle")
        .attr("r", 8);
    portEnter.append("text")
        .attr("dx", -3)
        .attr("dy", 3)
        .text(function(d) { return trim_zero(d.port_no); });
};


elem.update_dij = function () {
    this.force
        .nodes(topo.nodes)
        .links(topo.links)
        .start();

    this.link = this.link.data(topo.links);
    this.link.exit().remove();
    this.link.enter().append("line")
        .attr("id", function (d) {return "p" + d.source.dpid + d.target.dpid;})//每条链接加上ID
        //.attr("id_h", function (d) {return "p" + d.source.dpid + d.target.ip;})//主机与交换机的连接
        .attr("class", "link");
    var len = topo.links.length;
    //var len_c=topo.childlinks.length;
    //var id_l=new Array;
    var len_r_s = topo.root_set.length;
    //for(var i=0;i<len-len_c;i++){
    //    id_l[i]="p" + topo.links[i].port.src.dpid + topo.links[i].port.dst.dpid;//链路ID
    //}
    //for(var j=len-len_c;j<len;j++){
    //    id_l[j]="p" + topo.links[j].port.src.dpid + topo.links[j].port.dst.ip;//主机链路ID
    //}
    for(var j=0;j<len;j++) {
        var id_l_i ="p" + topo.links[j].port.src.dpid + topo.links[j].port.dst.dpid;//链路ID;
        //console.log('124-id_l_i:'+id_l_i);
        if (len_r_s == 0) {
            d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
            //d3.select("#" + id_l_i).attr("style", "stroke:rgb(169,169,169)");//默认颜色
        }
        else {
            for (var i = 0; i < len_r_s; i++) {
                var id_c = "p" + topo.root_set[i].port.src.dpid + topo.root_set[i].port.dst.dpid;//需要变色的ID
                var id_c_2 = "p" + topo.root_set[i].port.dst.dpid + topo.root_set[i].port.src.dpid;//需要变色的ID
                //console.log('130-id_c:'+id_c);
                if (id_l_i == id_c || id_l_i==id_c_2) {
                    d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,255,0)");
                    //d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
                    break;
                }
                else {
                    d3.select("#" + id_l_i).attr("style", "stroke:rgb(0,0,139)");
                    //d3.select("#" + id_l_i).attr("style", "stroke:rgb(169,169,169)");//默认颜色
                }
            }
        }
    }

    this.node = this.node.data(topo.nodes);
    this.node.exit().remove();
    var nodeEnter = this.node.enter().append("g")
        .attr("class", "node")
        .on("dblclick", function(d) { d3.select(this).classed("fixed", d.fixed = false); })
        .call(this.drag);
    nodeEnter.append("image")
        .attr("xlink:href", function(d){
            //console.log(d.dpid);
            //  console.log(d.ipv4);
            if (d.dpid ==undefined )
                return "./image/router_red.png";
            else return"./image/router.png"})
        .attr("x", -CONF.image.width/2)
        .attr("y", -CONF.image.height/2)
        .attr("width", CONF.image.width)
        .attr("height", CONF.image.height);
    nodeEnter.append("text")
        .attr("dx", -CONF.image.width/2)
        .attr("dy", CONF.image.height-10)
        .text(function(d) {
            if (d.dpid ==undefined )
                return     "ipv4: " + trim_zero(d.ipv4);
            else return  "dpid: " + sixteen_to_ten(d.dpid)
   });

    var ports = topo.get_ports();
    this.port.remove();
    this.port = this.svg.selectAll(".port").data(ports);
    var portEnter = this.port.enter().append("g")
        .attr("class", "port");
    portEnter.append("circle")
        .attr("r", 8);
    portEnter.append("text")
        .attr("dx", -3)
        .attr("dy", 3)
        .text(function(d) { return trim_zero(d.port_no); });
};


function is_valid_link(link) {
    return (link.src.dpid < link.dst.dpid)
}
function is_valid1_link(link) {            //交换机与
    return (link.src.dpid < link.dst.ip)
}

var topo = {
    nodes:[],
    links: [],
    hosts:[],
    childlinks:[],
    root_set:[],
    root_set_dij:[],
    node_index: {}, // dpid -> index of nodes array
    host_index:{},
    initialize: function (data) {
        this.add_nodes(data.switches);
        //this.add_hosts(data.hosts);
        this.add_links(data.links);
        //this.add_childLinks(data.childlinks);
    },
    add_nodes: function (nodes) {
        //console.log(JSON.stringify(nodes));
        for (var i = 0; i < nodes.length; i++) {
            this.nodes.push(nodes[i]);
        }
        this.refresh_node_index();
    },
    add_hosts: function (nodes) {
        for (var i = 0; i < nodes.length; i++) {
             //console.log("add hosts: " + JSON.stringify(links[i]));
            this.hosts.push(nodes[i]);
            //this.nodes.push(nodes[i]);
        }
     Array.prototype.push.apply(this.nodes, this.hosts);
         // //this.refresh_host_index();
    },
    add_links: function (links) {
        //console.log(JSON.stringify(links));
        for (var i = 0; i < links.length; i++) {
            if (!is_valid_link(links[i])) continue;
            //console.log("add link: " + JSON.stringify(links[i]));
            var src_dpid = links[i].src.dpid;
            var dst_dpid = links[i].dst.dpid;
            var src_index = this.node_index[src_dpid];
            var dst_index = this.node_index[dst_dpid];
            var link = {
                source: src_index,
                target: dst_index,
                port: {
                    src: links[i].src,
                    dst: links[i].dst
                }
            }
            this.links.push(link);
            //console.log('350-this.links'+JSON.stringify(this.links));
        }
    },
    add_routelink:function(links){
        //console.log("route set link: before for "+JSON.stringify(links));
        //console.log("route set link: before for "+links);
        for (var i = 0; i < links[0].length; i++) {
            //if (!is_valid_link(links[i])) continue;
            //console.log("root set link: " + JSON.stringify(links[0][i]));
            var src_dpid = links[0][i].src_dpid;
            var dst_dpid = links[0][i].dst_dpid;
            var src_index = this.node_index[src_dpid];
            var dst_index = this.node_index[dst_dpid];
            var link = {
                source: src_index,
                target: dst_index,
                port: {
                    src: {
                        'dpid':src_dpid
                    },
                    dst: {
                        'dpid':dst_dpid
                    }
                }
            }
            this.root_set.push(link);
            console.log('370:'+JSON.stringify(this.root_set));
            //console.log(JSON.stringify('topo.root_set:'+JSON.stringify(this.root_set)));
        }
    },
    add_routelink_dij:function(links){
        //console.log("route set link: before for "+JSON.stringify(links));
        //console.log("route set link: before for "+links);
        for (var i = 0; i < links[0].length; i++) {
            //if (!is_valid_link(links[i])) continue;
            console.log("root set link dij: " + JSON.stringify(links[0][i]));
            var src_dpid = links[0][i].src_dpid;
            var dst_dpid = links[0][i].dst_dpid;
            var src_index = this.node_index[src_dpid];
            var dst_index = this.node_index[dst_dpid];
            var link = {
                source: src_index,
                target: dst_index,
                port: {
                    src: {
                        'dpid':src_dpid
                    },
                    dst: {
                        'dpid':dst_dpid
                    }
                }
            }
            console.log('368:'+JSON.stringify(link));
            this.root_set_dij.push(link);
            //console.log(JSON.stringify('topo.root_set:'+JSON.stringify(this.root_set)));
        }
    },
     add_childLinks: function (links) {
        for (var i = 0; i < links.length; i++) {
            if (!is_valid1_link(links[i])) continue;
            console.log("add childlink: " + JSON.stringify(links[i]));
            var src_index = this.node_index[src_dpid];
            var dst_index = this.node_index[dst_ip];              //该成ip
            var link = {
                source: src_index,
                target: dst_index,
                port: {
                    src: links[i].src,
                    dst: links[i].dst
                }
            }
            this.childlinks.push(link);
        }
         Array.prototype.push.apply(this.links, this.childlinks);
            var src_dpid = links[i].src.dpid;
            var dst_ip = links[i].dst.ip;
    },
    delete_nodes: function (nodes) {
        for (var i = 0; i < nodes.length; i++) {
            console.log("delete switch: " + JSON.stringify(nodes[i]));

            node_index = this.get_node_index(nodes[i]);
            this.nodes.splice(node_index, 1);
        }
        this.refresh_node_index();
    },
    delete_links: function (links) {
        for (var i = 0; i < links.length; i++) {
            if (!is_valid_link(links[i])) continue;
            console.log("delete link: " + JSON.stringify(links[i]));

            link_index = this.get_link_index(links[i]);
            this.links.splice(link_index, 1);
        }
    },
    get_node_index: function (node) {
        for (var i = 0; i < this.nodes.length; i++) {
            if (node.dpid == this.nodes[i].dpid) {
                return i;
            }
        }
        return null;
    },
    get_link_index: function (link) {
        for (var i = 0; i < this.links.length; i++) {
            if (link.src.dpid == this.links[i].port.src.dpid &&
                    link.src.port_no == this.links[i].port.src.port_no &&
                    link.dst.dpid == this.links[i].port.dst.dpid &&
                    link.dst.port_no == this.links[i].port.dst.port_no) {
                return i;
            }
        }
        return null;
    },
    get_ports: function () {
        var ports = [];
        var pushed = {};
        for (var i = 0; i < this.links.length; i++) {
            function _push(p, dir) {
                key = p.dpid + ":" + p.port_no;
                if (key in pushed) {
                    return 0;
                }

                pushed[key] = true;
                p.link_idx = i;
                p.link_dir = dir;
                return ports.push(p);
            }
            _push(this.links[i].port.src, "source");
            _push(this.links[i].port.dst, "target");
        }

        return ports;
    },
    get_port_point: function (d) {
        var weight = 0.88;

        var link = this.links[d.link_idx];
        var x1 = link.source.x;
        var y1 = link.source.y;
        var x2 = link.target.x;
        var y2 = link.target.y;

        if (d.link_dir == "target") weight = 1.0 - weight;

        var x = x1 * weight + x2 * (1.0 - weight);
        var y = y1 * weight + y2 * (1.0 - weight);

        return {x: x, y: y};
    },
    refresh_node_index: function(){
        this.node_index = {};
        for (var i = 0; i < this.nodes.length; i++) {
            this.node_index[this.nodes[i].dpid] = i;
        }
        //console.log(JSON.stringify(this.node_index));
    },
     refresh_host_index: function(){
        this.host_index = {};
        for (var i = 0; i < this.host.length; i++) {
            this.host_index[this.host[i].dpid] = i;
        }
    },
}

var rpc = {
    event_switch_enter: function (params) {
        var switches = [];
        for(var i=0; i < params.length; i++){
            switches.push({"dpid":params[i].dpid,"ports":params[i].ports,});
        }
        topo.add_nodes(switches);
        elem.update();
        return "";
    },
    event_switch_leave: function (params) {
        var switches = [];
        for(var i=0; i < params.length; i++){
            switches.push({"dpid":params[i].dpid,"ports":params[i].ports});
        }
        topo.delete_nodes(switches);
        elem.update();
        return "";
    },
    event_link_add: function (links) {
        console.log('event_link_add');
        topo.add_links(links);
        elem.update();
        return "";
    },
    event_link_delete: function (links) {
        console.log('event_link_delete');
        topo.delete_links(links);
        elem.update();
        return "";
    },
    event_route_set:function (links){                                     //路由建立响应事件
        console.log(JSON.stringify(links));
        topo.add_routelink(links);
        elem.update();
        console.log('OKKKKKKKKKKKKKKK!');
        return "";
    },
    event_route_set_dij:function (links){                                     //路由建立响应事件
        console.log(JSON.stringify(links));
        topo.add_routelink_dij(links);
        elem.update();
        console.log('dij OKKKKKKKKKKKKKKK!');
        return "";
    },
}

function initialize_topology() {
    d3.json("/v1.0/topology/switches", function(error, switches) {
        d3.json("/v1.0/topology/links", function(error, links) {
            topo.initialize({switches: switches, links: links});
            elem.update();
        });
    });
}

function main() {
    initialize_topology();
}

main();
