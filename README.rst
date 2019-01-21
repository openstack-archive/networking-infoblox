===============================
networking-infoblox
===============================

Contains Neutron drivers for integration with Infoblox grids for IPAM and DNS.

* Free software: Apache license
* Source: http://git.openstack.org/cgit/openstack/networking-infoblox
* Bugs: http://bugs.launchpad.net/networking-infoblox
* Installation: https://github.com/openstack/networking-infoblox/blob/master/doc/source/installation.rst
* Configuration Guide: https://github.com/openstack/networking-infoblox/blob/master/doc/source/configuration_guide.rst

Features
--------

This release of the driver supports:

* IPv4 and IPv6 Subnet creation, update and deletion
* IPv4 and IPv6 address allocation and deallocation
* Support for fixed and floating IP addresses
* Creation and deletion of Host, A, AAAA, and PTR records during IP allocation
* Creation of authoritative zones
* Support for GM and CP members and Cloud API
* Flexible mapping of OpenStack entities to network view
* Set EAs to populate the Cloud tab in the Infoblox UI
* Support for Neutron Rocky release (release 13.0.0 of the Driver)
* Authentication:

  - Support for keystone v3 configuration:

    a) Support for Domain scope authentication
    b) Support for Project scope authentication

  - Support for keystone SSL configuration

* Dropped support for OpenStack Ocata

Overview
--------

The IPAM driver consists of two components: the ``networking_infoblox`` Python
module, and the ``infoblox-ipam-agent``. Each of these depend upon the
``infoblox-client`` [#]_ library.

The IPAM driver will be consulted by Neutron whenever subnet or IP allocation
is needed. The driver will use RESTful API calls (aka, "Web-API" or "WAPI") to
perform these operations in Infoblox. Additionally, the driver will tag each
of these entities in Infoblox with various meta-data from OpenStack, such as
the tenant and the corresponding OpenStack IDs for the objects. This tagging
allows the entities to show up in the Cloud tab of the UI (which is available
with the Cloud Network Automation license), giving full visibility into the
OpenStack cloud from within Infoblox.

The agent serves a few functions. First, it will populate the local Neutron
database with data about the Infoblox grid. This enables the selection
of the member and the network view to be made when allocating subnets and IP
addresses, without additional WAPI calls. Second, it listens for events on
the OpenStack message bus, and makes WAPI calls related to objects that are
not directly part of the IPAM function. 

Installation and Configuration
------------------------------

See the documentation link above for details on Installation and Configuration.

Known issues
------------

1. When deploying an instance with a domain label exceeding 63 characters, an unknown
   host record name appears in the zone on NIOS. This is due to the NIOS restriction
   of max 63 characters for domain labels.

2. If a DNS zone is deleted, the corresponding network entry in NIOS must be deleted
   prior to running the synchronization tool. Otherwise the synchronization would fail.

3. If a host record from a DNS zone is deleted, the corresponding port entry in NIOS
   must be deleted prior to running the synchronization tool. Otherwise the synchronization
   would fail.

4. Once the IPAM driver create a Network View on Infoblox, the name of the Network
   View should not be changed. Changing Network View name on Infoblox would result
   in data synchronization issue. This will be addressed in a future release of the
   IPAM driver.

5. If the ``Default Domain Name Pattern`` includes one of the following patterns:
   ``{tenant_name}``, ``{network_name}`` or ``{subnet_name}``, the names of
   of the corresponding objects should not be changed in OpenStack once they are
   created. Changing them would result in data synchronization issue. This will be
   addressed in a future release of the IPAM driver.

.. [#] https://pypi.python.org/pypi/infoblox-client
