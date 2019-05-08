
import itertools

def connect_instances(instances, eps=1):
    nr_connections = 0
    # todo add check if IFC has port information -> decision system
    for instance1, instance2 in itertools.combinations(instances, 2):
        for port1 in instance1.ports:
            for port2 in instance2.ports:
                delta = port1.position - port2.position
                if max(abs(delta)) < eps:
                    port1.connect(port2)
                    port2.connect(port1)
                    nr_connections += 1

    return nr_connections

