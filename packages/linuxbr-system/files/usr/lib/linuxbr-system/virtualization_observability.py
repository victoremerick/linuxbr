"""Libvirt performance counters and observed virtual network paths."""
from datetime import datetime
import time
import xml.etree.ElementTree as ET


def attribute(node, path, name, default=''):
    item = node.find(path)
    return default if item is None else item.get(name, default)


def device_totals(domain, devices, function, field_count):
    totals = [0] * field_count
    method = getattr(domain, function, None)
    if not devices or method is None:
        return None
    for device in devices:
        try:
            values = method(device)
        except Exception:
            # Libvirt drivers can omit counters for a device or guest state.
            return None
        for index in range(field_count):
            value = values[index]
            totals[index] = totals[index] + value if value >= 0 and totals[index] is not None else None
    return tuple(totals)


def sample(domain):
    _, maximum, memory, cpus, cpu_ns = domain.info()
    now = time.monotonic()
    result = dict(timestamp=now, time=datetime.now().astimezone().isoformat(timespec='seconds'),
                  active=bool(domain.isActive()), cpu=cpu_ns, cpus=cpus,
                  memory=memory, maximum=maximum, actual=None, disk=None, net=None)
    if not result['active']:
        return result
    root = ET.fromstring(domain.XMLDesc(0))
    disks = [item.get('dev') for item in root.findall("devices/disk[@device='disk']/target") if item.get('dev')]
    nics = [item.get('dev') for item in root.findall('devices/interface/target') if item.get('dev')]
    result['disk'] = device_totals(domain, disks, 'blockStats', 5)
    result['net'] = device_totals(domain, nics, 'interfaceStats', 8)
    try:
        stats = domain.memoryStats()
    except Exception:
        # Balloon memory counters are optional across hosts and guest models.
        stats = {}
    if 'available' in stats and 'unused' in stats:
        result['actual'] = max(0, stats['available'] - stats['unused'])
    return result


def rates(previous, current):
    result = dict(cpu=None, read=None, write=None, rx=None, tx=None)
    elapsed = current['timestamp'] - previous['timestamp'] if previous else 0
    if not previous or elapsed <= 0 or not (previous['active'] and current['active']):
        return result
    if current['cpu'] >= previous['cpu'] and current['cpus'] == previous['cpus']:
        result['cpu'] = min(100.0, (current['cpu'] - previous['cpu']) / elapsed / max(1, current['cpus']) / 1e7)
    for key, field, index in (('read', 'disk', 1), ('write', 'disk', 3), ('rx', 'net', 0), ('tx', 'net', 4)):
        old, new = previous[field], current[field]
        if old and new and old[index] is not None and new[index] is not None and new[index] >= old[index]:
            result[key] = (new[index] - old[index]) / elapsed
    return result


def bridge_ports(connection, name):
    if not name or not hasattr(connection, 'interfaceLookupByName'):
        return []
    try:
        root = ET.fromstring(connection.interfaceLookupByName(name).XMLDesc(0))
    except Exception:
        return []
    result = []
    for port in root.findall('bridge/interface'):
        label = attribute(port, 'vlan/interface', 'name') or port.get('name', '')
        tag = attribute(port, 'vlan', 'tag')
        result.append(f'{label} (VLAN {tag})' if tag else label)
    return [label for label in result if label]


def topology(manager):
    rows = []
    networks = {row['name']: ET.fromstring(row['xml']) for row in manager.networks()}
    for domain in manager.connection.listAllDomains(0):
        root = ET.fromstring(domain.XMLDesc(0))
        for nic in root.findall('devices/interface'):
            name = attribute(nic, 'source', 'network')
            network = networks.get(name)
            forward = network.find('forward') if network is not None else None
            bridge = attribute(nic, 'source', 'bridge')
            if network is not None:
                bridge = bridge or attribute(network, 'bridge', 'name')
            upstream = attribute(nic, 'source', 'dev')
            if forward is not None:
                upstream = upstream or forward.get('dev') or ', '.join(
                    node.get('dev', '') for node in forward.findall('interface') if node.get('dev'))
            ports = bridge_ports(manager.connection, bridge)
            upstream = upstream or ', '.join(ports)
            mode = forward.get('mode', '') if forward is not None else nic.get('type', '')
            if not upstream:
                upstream = 'Rota do hospedeiro' if mode in ('nat', 'route', 'open', 'user') else '—'
            group = attribute(nic, 'source', 'portgroup')
            tags = nic.findall('vlan/tag')
            if not tags and network is not None:
                port_group = next((item for item in network.findall('portgroup')
                                   if (item.get('name') == group if group else item.get('default') == 'yes')), None)
                if port_group is not None:
                    tags = port_group.findall('vlan/tag')
                tags = tags or network.findall('vlan/tag')
            rows.append(dict(vm=domain.name(), interface=attribute(nic, 'target', 'dev') or
                             attribute(nic, 'mac', 'address') or '—', kind=mode, network=name or '—',
                             bridge=bridge or '—', vlan=', '.join(tag.get('id', '') for tag in tags) or '—',
                             upstream=upstream))
    return sorted(rows, key=lambda row: (row['vm'].casefold(), row['interface']))
