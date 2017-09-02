from ryu.topology import switches


class Device(switches.Switch):
    def __init__(self, dp):
        super(Device, self).__init__(dp)

        self.name = None

        # ports[port_no] = Port
        # overshadow super.ports
        self.ports = {}

