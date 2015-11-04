# Copyright 2015 Infoblox Inc.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from infoblox_client import objects as ib_objects


def get_ea_for_network_view(tenant_id):
    """Generates EAs for Network View.

    :param tenant_id: tenant_id
    :return: dict with extensible attributes ready to be sent as part of
    NIOS WAPI
    """
    # OpenStack should not own entire network view,
    # since shared or external networks may be created in it
    attributes = {'Tenant ID': tenant_id,
                  'Cloud API Owned': False}
    return ib_objects.EA(attributes)


def get_ea_for_network(user_id, tenant_id, network, subnet):
    """Generates EAs for Network.

    :param user_id: user_id
    :param tenant_id: tenant_id
    :param subnet: neutron subnet object
    :param network: neutron network object
    :return: dict with extensible attributes ready to be sent as part of
    NIOS WAPI
    """
    subnet = {} if subnet is None else subnet
    network = {} if network is None else network

    subnet_id = subnet.get('id')
    subnet_name = subnet.get('name')

    network_id = network.get('id')
    network_name = network.get('name')

    network_type = network.get('provider:network_type')
    physical_network = network.get('provider:physical_network')
    segmentation_id = network.get('provider:segmentation_id')

    attributes = {'Subnet ID': subnet_id,
                  'Subnet Name': subnet_name,
                  'Network ID': network_id,
                  'Network Name': network_name,
                  'Network Encap': network_type,
                  'Segmentation ID': segmentation_id,
                  'Physical Network Name': physical_network}

    common_ea = get_common_ea(network, user_id, tenant_id, for_network=True)
    attributes.update(common_ea)

    return ib_objects.EA(attributes)


def get_ea_for_range(user_id, tenant_id, network):
    return ib_objects.EA(get_common_ea(network, user_id, tenant_id))


def get_dict_for_ip(port_id, device_owner, device_id,
                    vm_id, ip_type):
    return {'Port ID': port_id,
            'Port Attached Device - Device Owner': device_owner,
            'Port Attached Device - Device ID': device_id,
            'VM ID': vm_id,
            'IP Type': ip_type}


def get_default_ea_for_ip(user_id, tenant_id):
    common_ea = get_common_ea(None, user_id, tenant_id)
    ip_dict = get_dict_for_ip(None, None, None, None, 'Fixed')
    common_ea.update(ip_dict)
    return ib_objects.EA(common_ea)


def get_ea_for_ip(user_id, tenant_id, network, port_id, device_id,
                  device_owner):
    # for gateway ip, no instance id exists
    instance_id = device_id
    common_ea = get_common_ea(network, user_id, tenant_id)
    ip_dict = get_dict_for_ip(port_id, device_owner, device_id,
                              instance_id, 'Fixed')
    common_ea.update(ip_dict)
    return ib_objects.EA(common_ea)


def get_ea_for_floatingip(user_id, tenant_id, network, port_id, device_id,
                          device_owner, instance_id):
    common_ea = get_common_ea(network, user_id, tenant_id)
    ip_dict = get_dict_for_ip(port_id, device_owner, device_id,
                              instance_id, 'Floating')
    common_ea.update(ip_dict)
    return ib_objects.EA(common_ea)


def get_ea_for_zone(user_id, tenant_id, network=None):
    return ib_objects.EA(get_common_ea(network, user_id, tenant_id))


def get_common_ea(network, user_id, tenant_id, for_network=False):
    if network:
        is_external = network.get('router:external', False)
        is_shared = network.get('shared')
    else:
        is_external = False
        is_shared = False

    is_cloud_owned = not (is_external or is_shared)
    ea_dict = {'Tenant ID': tenant_id,
               'Account': user_id,
               'Cloud API Owned': is_cloud_owned}
    if for_network:
        ea_dict['Is External'] = is_external
        ea_dict['Is Shared'] = is_shared
    return ea_dict
