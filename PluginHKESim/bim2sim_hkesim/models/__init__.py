"""Package for Python representations of HKESim models"""

from bim2sim.export.modelica import Interface, Model, System

class StaticPipe(Model):
    model = "Modelica.Fluid.Pipes.StaticPipe"

    def __init__(self, length, diameter, **kwargs):
        par = dict(
            length=length,
            diameter=diameter
        )
        self.port_a = Interface("port_a", self)
        self.port_b = Interface("port_b", self)
        inter = [self.port_a, self.port_b]

        super().__init__(par, inter, **kwargs)



if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)

    p1 = StaticPipe(name="pipe1", comment="test pipe", length=10, diameter=0.4)
    p2 = StaticPipe(name="pipe2", comment="test pipe", length=8, diameter=0.3)

    s = System("Testbed", "test")

    s.children.append(p1)
    s.children.append(p2)

    p1.port_a.connect(p2.port_b)
    print(s)
    s.save("C:\\Entwicklung\\temp")
