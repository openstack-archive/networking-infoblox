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

from neutron.api.v2 import attributes
from neutron.common import constants as n_const
from neutron.extensions import external_net
from neutron.extensions import providernet

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils


def get_ea_for_network_view(tenant_id, tenant_name, cloud_adapter_id):
    """Generates EAs for Network View.

    :param tenant_id: tenant_id
    :param tenant_name: tenant_name
    :return: dict with extensible attributes ready to be sent as part of
    NIOS WAPI
    """
    # OpenStack should not own entire network view,
    # since shared or external networks may be created in it
    attributes = {const.EA_CMP_TYPE: const.CLOUD_PLATFORM_NAME,
                  const.EA_TENANT_ID: tenant_id or const.EA_RESET_VALUE,
                  const.EA_TENANT_NAME: tenant_name,
                  const.EA_CLOUD_API_OWNED: 'False',
                  const.EA_CLOUD_ADAPTER_ID: str(cloud_adapter_id)}
    return ib_objects.EA(attributes)


def get_net_specific_eas(network):
    """Generates Network specific EAs

    :param network: neutron network object
    :return: dict with network specific extensible attributes
    """
    if not network:
        return {}
    network_type = network.get(providernet.NETWORK_TYPE)
    physical_network = network.get(providernet.PHYSICAL_NETWORK)
    segmentation_id = network.get(providernet.SEGMENTATION_ID)
    return {const.EA_NETWORK_ID: network.get('id'),
            const.EA_NETWORK_NAME: network.get('name'),
            const.EA_NETWORK_ENCAP: network_type,
            const.EA_SEGMENTATION_ID: segmentation_id,
            const.EA_PHYSICAL_NETWORK_NAME: physical_network}


def get_subnet_specific_eas(subnet):
    """Generates subnet specific EAs

    :param subnet: neutron network object
    :return: dict with subnet specific extensible attributes
    """
    if not subnet:
        return {}
    return {const.EA_SUBNET_ID: subnet.get('id'),
            const.EA_SUBNET_NAME: subnet.get('name')}


def get_ea_for_network(user_id, tenant_id, tenant_name, network, subnet):
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

    attributes = get_subnet_specific_eas(subnet)
    attributes.update(get_net_specific_eas(network))

    common_ea = get_common_ea(network, user_id, tenant_id,
                              tenant_name, for_network=True)
    attributes.update(common_ea)

    return ib_objects.EA(attributes)


def reset_ea_for_network(ib_network):
    if not ib_network or not ib_network.extattrs:
        return

    utils.reset_required_eas(ib_network)

    eas = ib_network.extattrs
    ea_dict = eas.to_dict()
    map(lambda ea: ea_dict.pop(ea, None), const.NETWORK_EA_LIST)
    ib_network.extattrs = ib_objects.EA.from_dict(ea_dict)


def get_ea_for_range(user_id, tenant_id, tenant_name, network):
    return ib_objects.EA(get_common_ea(network, user_id, tenant_id,
                                       tenant_name))


def reset_ea_for_range(ib_range):
    if not ib_range or not ib_range.extattrs:
        return

    utils.reset_required_eas(ib_range)

    eas = ib_range.extattrs
    ea_dict = eas.to_dict()
    map(lambda ea: ea_dict.pop(ea, None), const.RANGE_EA_LIST)
    ib_range.extattrs = ib_objects.EA.from_dict(ea_dict)


def get_dict_for_ip(port_id, device_owner, device_id,
                    vm_id, ip_type, instance_name=None):
    return {const.EA_PORT_ID: port_id,
            const.EA_PORT_DEVICE_OWNER: device_owner,
            const.EA_PORT_DEVICE_ID: device_id,
            const.EA_VM_ID: vm_id,
            const.EA_IP_TYPE: ip_type,
            const.EA_VM_NAME: instance_name}


def get_default_ea_for_ip(user_id, tenant_id, tenant_name):
    common_ea = get_common_ea(None, user_id, tenant_id, tenant_name)
    ip_dict = get_dict_for_ip(None, None, None, None, const.IP_TYPE_FIXED)
    common_ea.update(ip_dict)
    return ib_objects.EA(common_ea)


def get_ea_for_ip(user_id, tenant_id, tenant_name, network, port_id, device_id,
                  device_owner, is_floating_ip=False, instance_name=None):
    instance_id = None
    ip_type = const.IP_TYPE_FIXED
    if is_floating_ip or device_owner == n_const.DEVICE_OWNER_FLOATINGIP:
        ip_type = const.IP_TYPE_FLOATING
    if device_owner in const.NEUTRON_DEVICE_OWNER_COMPUTE_LIST:
        instance_id = device_id

    common_ea = get_common_ea(network, user_id, tenant_id, tenant_name)
    ip_dict = get_dict_for_ip(port_id, device_owner, device_id,
                              instance_id, ip_type, instance_name)
    common_ea.update(ip_dict)
    return ib_objects.EA(common_ea)


def get_ea_for_reverse_zone(user_id, tenant_id, tenant_name, network, subnet):
    ea_dict = get_common_ea(network, user_id, tenant_id, tenant_name)
    ea_dict.update(get_net_specific_eas(network))
    ea_dict.update(get_subnet_specific_eas(subnet))
    return ib_objects.EA(ea_dict)


def get_ea_for_forward_zone(user_id, tenant_id, tenant_name, network, subnet,
                            name_template):
    ea_dict = get_common_ea(network, user_id, tenant_id, tenant_name)
    if '{subnet_id}' in name_template or '{subnet_name}' in name_template:
        ea_dict.update(get_subnet_specific_eas(subnet))
        ea_dict.update(get_net_specific_eas(network))
    elif '{network_id}' in name_template or '{network_name}' in name_template:
        ea_dict.update(get_net_specific_eas(network))
    return ib_objects.EA(ea_dict)


def reset_ea_for_zone(ib_zone):
    if not ib_zone or not ib_zone.extattrs:
        return

    utils.reset_required_eas(ib_zone)

    eas = ib_zone.extattrs
    ea_dict = eas.to_dict()
    map(lambda ea: ea_dict.pop(ea, None), const.ZONE_EA_LIST)
    ib_zone.extattrs = ib_objects.EA.from_dict(ea_dict)


def get_common_ea(network, user_id, tenant_id, tenant_name, for_network=False):
    if network:
        is_external = network.get(external_net.EXTERNAL, False)
        is_shared = network.get(attributes.SHARED)
    else:
        is_external = False
        is_shared = False

    is_cloud_owned = not (is_external or is_shared)
    ea_dict = {const.EA_CMP_TYPE: const.CLOUD_PLATFORM_NAME,
               const.EA_TENANT_ID: tenant_id or const.EA_RESET_VALUE,
               const.EA_TENANT_NAME: tenant_name,
               const.EA_ACCOUNT: user_id,
               const.EA_CLOUD_API_OWNED: str(is_cloud_owned)}
    if for_network:
        ea_dict[const.EA_IS_EXTERNAL] = str(is_external)
        ea_dict[const.EA_IS_SHARED] = str(is_shared)
    return ea_dict
