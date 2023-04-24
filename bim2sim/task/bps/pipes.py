import pandapipes as pp

net = pp.create_empty_network(fluid="water", name="example_net")
# Erstellen der Knoten (Nodes)
# create source node
source = pp.create_ext_grid(net, 0.1, name="Source")

# create two sink nodes
sink1 = pp.create_sink(net, 0.5, name="Sink1")
sink2 = pp.create_sink(net, 0.5, name="Sink2")