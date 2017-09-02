bits = 1
Kilobits = 1000*bits
Megabits = 1000*Kilobits
Gigabits = 1000*Megabits
Terabits = 1000*Gigabits

Bytes = 8*bits
KiloBytes = 1024*Bytes
MegaBytes = 1024*KiloBytes
GigaBytes = 1024*MegaBytes
TeraBytes = 1024*GigaBytes


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)


def find_packet(pkt, target):
    """
        try to extract the packet and find for specific
        protocol.
    """
    for packets in pkt.protocols:
        try:
            if packets.protocol_name == target:
                return packets
        except AttributeError:
            pass
    return None


def unicode_fmt(i):
    """format unicode object in dict & list to string or int

    :param i: dict/list object with unicode object
    :return: formatted object
    """
    if isinstance(i, dict):
        return {unicode_fmt(key): unicode_fmt(value) for key, value in i.iteritems()}
    elif isinstance(i, list):
        return [unicode_fmt(element) for element in i]
    elif isinstance(i, unicode):
        return i.encode('utf-8')
    elif isinstance(i, int):
        return int(i)
    else:
        return i
