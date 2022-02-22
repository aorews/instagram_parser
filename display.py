import networkx as nx
import numpy as np
import argparse
import itertools
from pyvis import network as net
from parse import Graph, Node


def get_largest_component(G):
    G1 = G.copy()
    G1.remove_nodes_from(set(G.nodes) - sorted(nx.connected_components(G), key=len, reverse=True)[0])
    return G1

def draw_pyvis(G):
    pyvis_graph = net.Network(height='1000px', width='100%', bgcolor='#222222', font_color='white')
    pyvis_graph.set_options("""
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -10050,
          "centralGravity": 0,
          "springLength": 120,
          "springConstant": 0.025,
          "damping": 1,
          "avoidOverlap": 1
        },
        "minVelocity": 0.75
      }
    }
    """)
    pyvis_graph.from_nx(G)
    #pyvis_graph.show_buttons(filter_=['physics'])
    pyvis_graph.save_graph(f'{args.path.split(".pkl")[0]}.html')

def assign_param(G, param, values):
    for node in G.nodes:
        G.nodes[node][param] = values[node]
    return G

def centralities(G):
    degree = nx.degree_centrality(G)
    closeness = nx.closeness_centrality(G)
    betweenness = nx.betweenness_centrality(G)

    ans =  {
        'degree': degree,
        'closeness': closeness,
        'betweenness': betweenness
    }
    for k, v in ans.items():
        ans[k] = {a: round(100 * b) for a,b in v.items()}
    return ans

def edge_betweenness(G, n):
    if n == 1:
        return {node: 0 for node in G.nodes}
    divisions = nx.algorithms.community.girvan_newman(G)
    limited = itertools.takewhile(lambda c: len(c) <= n, divisions)
    for item in limited:
        data = dict()
        for node in G.nodes:
            for i, group in enumerate(item):
                if node in group:
                    data[node] = i
    return data

def parse_args():
    def pair(arg):
        arg = [x for x in arg.split(',')]
        if arg[0] == '' or arg[1] == '':
            raise Exception('Incorrect credentials')
        return arg

    parser = argparse.ArgumentParser('Provide path to saved graph')
    parser.add_argument('--path', type = str, required = True, help = 'Provide path to parsed graph')
    parser.add_argument('--node_size', type = str, nargs = '?', const = 'likes', default = 'likes', help = 'likes or betweenness')
    parser.add_argument('--clusters', type = int, nargs = '?', const = 6, default = 6, help = 'Amount of clusters in largest component of the graph for Girvan Newman algorithm')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    graph = Graph.load(args.path)

    G = nx.from_edgelist(graph.edges)
    G.add_nodes_from([x.id for x in graph.nodes])

    # Relabel from ids to usernames
    G = nx.relabel_nodes(G, {x.id:x.nickname for x in graph.nodes})

    # Reshape
    G = assign_param(G, 'shape', {x.nickname: 'star' if x.is_popular else 'image' if x.is_ghost else 'dot' for x in graph.nodes})

    # Show likes amount
    G = assign_param(G, 'title', {x.nickname: f"Likes: {x.likes}" for x in graph.nodes})

    # Add images for ghosts
    G = assign_param(G, 'image', {x.nickname: "https://cdn.iconscout.com/icon/premium/png-256-thumb/ghost-2605978-2182119.png" for x in graph.nodes})

    # Get clusters with Girvan Newman algorithm
    G = assign_param(G, 'group', {x.nickname: -1 for x in graph.nodes})
    G_largest = get_largest_component(G)
    G_largest = assign_param(G_largest, 'group', edge_betweenness(G_largest, args.clusters))

    # Assign size of nodes
    if args.node_size == 'likes':
        max_likes = max([x.likes for x in graph.nodes])
        size_dict = {
            x.nickname: 10 + 
            10 * (x.likes/max_likes) * (3 if x.is_ghost else 1)
            for x in graph.nodes
            }
        G = assign_param(G, 'size', size_dict)

    elif args.node_size == 'betweenness':
        G = assign_param(G, 'size', {node.nickname: 10 for node in graph.nodes})
        c = centralities(G_largest)
        G_largest = assign_param(G_largest, 'size', {k: 10 + v for k, v in c['betweenness'].items()})

    G = nx.compose(G, G_largest)
    draw_pyvis(G)
