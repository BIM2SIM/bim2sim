class components:
    def __init__(self):
        self.name = 'components'
        self.boiler = self.boiler()
    class space_heaters():
        pass

    class pipes():
        def __init__(self,
                    parent,
                    name,
                    length,
                    diameter,
                    connected_to,
                    ):
            self.parent = parent
            self.name = name
            self.length = length
            self.diameter = diameter
            self.connected_to = connected_to

    class boiler():
        def __init__(
                self,
                parent,
                name,
                rated_power,
                min_power,
                volume,
                efficiency,
                ):
            self.parent = parent
            self.name = name
            self.rated_power = rated_power
            self.min_power = min_power
            self.volume = volume
            self.efficiency = efficiency

if __name__ == '__main__':
    components = components()
    print(components.name)