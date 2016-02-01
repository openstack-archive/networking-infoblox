============
Installation
============
The Infoblox driver should be installed on the controller nodes that are
runing your ``neutron-server``. The installation consists of the following
basic steps:

1) Configure Infoblox
2) Install the driver module on the controller nodes
3) Run database migrations to create the Infoblox tables
4) Modify neutron.conf and nova.conf
5) Start the Infoblox IPAM Agent
6) Restart the neutron-server
7) Restart nova-compute services


Configure Infoblox
==================
There are four steps to setting up your Infoblox grid to work with the IPAM
driver.

    a) Add a user and optionally a group, and configure permissions
    b) Create Extensible Attribute definitions with the create_ea_defs.py script
    c) Set the EAs to values representing the desired behavior
    d) Tag members that should serve OpenStack domains

Creating the User
-----------------
First, you should create a user for the integration. If you have a Cloud
Network Automation license, this user should be assigned to the Cloud API Only
admin group. Otherwise, you may want to create a group specifically for this
integration. The group must be given the following permissions:

.. list-table::
   :header-rows: 1
   :widths: 30 30 30 10

   * - Permission Type
     - Resource
     - Resource Type
     - Permission
   * - [DNS]
     - All A Records
     - A record
     - RW
   * - [DNS]
     - All AAAA Records
     - AAAA record
     - RW
   * - [DNS, DHCP, IPAM]
     - All Hosts
     - Host
     - RW
   * - [DHCP, DNS, IPAM]
     - All IPv4 Host Addresses
     - IPv4 Host address
     - RW
   * - [DHCP, DNS, IPAM]
     - All IPv6 Host Addresses
     - IPv6 Host address
     - RW
   * - [DHCP, IPAM]
     - All IPv6 Networks
     - IPv6 Network
     - RW
   * - [GRID]
     - All Members
     - Member
     - RW
   * - [DHCP, IPAM]
     - All IPv4 Networks
     - IPv4 Network
     - RW
   * - [DHCP, IPAM]
     - All Network Views
     - Network view
     - RW
   * - [DNS]
     - All PTR Records
     - PTR record
     - RW
   * - [DHCP]
     - All IPv4 Ranges
     - IPv4 range
     - RW
   * - [CLOUD]
     - All Tenants
     - Tenant
     - RW
   * - [DNS]
     - All DNS Views
     - DNS View
     - RW
   * - [DNS]
     - All Zones
     - Zone
     - RW

Create Extensible Attribute Definitions
---------------------------------------
The driver uses a variety of Extensible Attributes (EAs) to manage its
configuration. The needed extensible attributes may be created automatically
using the ``create_ea_defs.py`` script that can be found under the ``tools``
directory in the distribution::

    $ python create_ea_defs.py

The script will prompt you for the user name and password of a superuser, which
is needed to create the EA definitions.

Setting EAs to Configure the Integration
----------------------------------------
You must decide on the configuration you would like to use. The details of each
option are in the configuration guide, however the most common options that
need to be configured are described here.

The configuration is captured within the various EAs that were created in the
previous step. In general, these EAs are set on the *grid master* member. To do
this, you navigate to Grid > Grid Manager > Members and click on the Gear icon
next to the grid master member. Choose the *Extensible Attributes* option. From
there you can create and modify various EA values that will apply to the entire
IPAM driver integration.

Network View Mapping
~~~~~~~~~~~~~~~~~~~~
When creating a new object in Infoblox, the IPAM driver must know the network
view in which to create the object. This is determined using a number of EAs.

In the simpliest form you can configure the driver to automatically create
network views as needed. The first EA that needs to be set is the
`Default Network View Scope`. This EA defines the default mapping to network
view when no mapping already exists within the Infoblox system. This can be
any of the following values:

1) ``Single``. This means that any time a pre-existing mapping cannot be found,
   the resulting object should be placed within a single, specific network
   view. That view should be specified with another EA, `Default Network View`.

2) ``Tenant``. This means that any time a pre-existing mapping cannot be found,
   the resulting object should be placed within a network view determined by
   the OpenStack tenant that owns the object. If no network view tagged with
   that Tenant ID exists, then a new network view will be created with the name
   ``tenant_name``.``tenant_id``.

3) ``Address Scope``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack address scope associated with the object.
   Address scopes are not fully supported in OpenStack Liberty, and so this
   value should not be used until a later version of the driver is available
   supporting this Mitaka feature.

4) ``Network``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack network. This is rarely used and primarily is
   provided for use in automated testing, where the same tenant may create
   multiple OpenStack Network entities with overlapping subnets.

5) ``Subnet``. This means that any time a pre-existing mapping cannot be
   found, the resulting object should be placed within a network view
   determined by the OpenStack subnet. This is rarely used, but can be
   necessary in certain deployments that utilize SDN plugins that allow
   spanning subnets across OpenStack Neutron installations.

Alternatively, You can pre-define mappings by creating a network view and then
tagging it with the name of a tenant, address scope, or network, in addition to CIDR of
a subnet. This can be done by creating the following EAs on a network view object.
Each of these EAs allows multiple values to be specified.

`Subnet CIDR Mapping` - If a subnet created matches one of the CIDR values specified
in this EA, the subnet will be created under this network view.

`Subnet ID Mapping` - If the ID of a subnet created matches one of the values specified
in this EA, the subnet will be created under this network view.

`Network Name Mapping` - If the name of a network matches one of the values specified
in this EA, the subnets within the network will be created under this network view.

`Network ID Mapping` - If the ID of a network matches one of the values specified
in this EA, the subnets within the network will be created under this network view.

`Tenant Name Mapping` - If the name of a tenant matches one of the values specified
in this EA, objects within the tenant will be created under this network view.

`Tenant ID Mapping` - If the ID of a tenant matches one of the values specified
in this EA, objects within the tenant will be created under this network view.

`Address Scope Name Mapping` - If the name of an address scope matches one of the
values specified in this EA, objects within the address scope will be created under
this network view.

`Address Scope ID Mapping` - If the ID of an address scope matches one of the
values specified in this EA, objects within the address scope will be created under
this network view.

Domain and Host Name Patterns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

`Default Domain Name Pattern`. This EA is used to control how domain names for
IP address allocations are determined. This EA can be set to a fixed string,
or can use patterns to generate unique zone names. For example, you may set
this to ``cloud.example.com`` to have all DNS entries within that domain. Or,
you can use substitution patterns: ``{tenant_name}.cloud.example.com`` would
place IPs associated with each tenant in their own domain.

For domain names, the following patterns are supported:

``{network_name}`` will be replaced with the OpenStack Network Name.

``{network_id}`` will be replaced with the OpenStack Network ID.

``{tenant_name}`` will be replaced with the OpenStack Tenant Name. Note that
for this to work, the `Tenant Name Persistence` EA must be set to True.

``{tenant_id}`` will be replaced with the OpenStack Tenant ID.
this name. For example, if all of your

``{subnet_name}`` will be replaced with the OpenStack Subnet Name.

``{subnet_id}`` will be replaced with the OpenStack Subnet ID.

`Default Host Name Pattern`. This EA controls host names in a manner similar to
the way `Default Domain Name Pattern` controls domain names. In addition to the
patterns supported for domain names, this EA supports these:

``{port_id}``. The port ID of the port associated with the IP.

``{instance_id}``. The Nova instance ID of the VM associated with the port.

``{instance_name}``. The Nova instance name of the VM associated with the port.

``{ip_address}``. The IP address for this port or host, with dots replaced by dashes.

``{ip_address_octet{n}}`` where n is a number 0-3. This is for IPv4 addresses
only. For example, if the pattern is
``host-{ip_address_octet{2}}-{ip_address_octet{3}}``
and the IP is 10.1.2.3, then the resulting hostname will be ``host-2-3``.

`Tenant Name Persistence`. Since Neutron does not have direct access to tenant
names (they are part of Keystone), the Infoblox IPAM agent can cache those
names it receives from the message bus. This reduces the Keystone API calls
needed to retrieve tenant name. This EA controls this behavior; it must be
set to True for tenant name support in domain or host names.


IP Allocation and DNS Record Creation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
`IP Allocation Strategy`. This EA is used to choose between Host Record and
Fixed Address for IP allocation. If chosen for Fixed Address, DNS records
associated with a fixed address are controlled by the additional EAs below.

`DNS Record Binding Types`. List of DNS records to generate and bind to a
fixed address during IP allocation. Supported DNS record types are 
``record:a`` (for A records), ``record:aaaa`` (for AAAA records), and
``record:ptr`` (for PTR records). This is a multi-value EA, with one of these
entries per value.

`DNS Record Unbinding Types`. List of DNS records to unbind from a
fixed address during IP deallocation. Supported DNS record types are the same
as `DNS Record Binding Types`.

`DNS Record Removable Types`. List of associated DNS records to delete when a
fixed address is deleted. This is typically a list of DNS records created
independently of the Infoblox IPAM Driver. Supported DNS record types are
``record:a``, ``record:aaaa``, ``record:ptr``, ``record:txt``, and
``record:cname``.

Identify Members to Use
-----------------------
In order to serve DHCP and DNS, you must pick grid members to be registered to
Neutron. You should exclude network discovery members and reporting members
since they cannot serve DHCP and DNS. For the members to serve DHCP and DNS,
the licenses must be properly installed and services must be properly running.

In general in order to utilize Infoblox for DHCP, you will need to use an SDN
solution that provides a DHCP relay function. The standard Neutron functions do
not provide relay.

To identify a grid member as available for use by OpenStack, you must set the
EA `Is Cloud Member` to True. If you are running with only a GM (not a full
grid), there is no need to set this value, as the GM will be used for all
protocol in that deployment model.

If you are running a grid but the GM is not configured and licensed for DNS or
DHCP, set `Use Grid Master for DHCP` EA on the GM object to False. This will
exclude the GM from being selected to serve DHCP or DHCP.

Installing the Driver
=====================
If you are installing the most recent production release, you can install
directly from PyPi. In that case, on each controller node that is running the
Neutron service, at the command line::

    $ sudo pip install networking-infoblox

Currently the version 2.x driver supports Liberty and Mitaka. You can download
the package from PyPi or from Launchpad, and install it via your chosen Python
package management system::

    $ sudo easy_install networking_infoblox-2.0.0-py2.7.egg

or::

    $ sudo wheel install networking_infoblox-2.0.0-py2-none-any.whl

Creating the Infoblox Neutron Database
======================================
The driver uses a number of different Infoblox-specific tables to manage the
integration. These are created by running the `neutron-db-manage` after you
install the `networking_infoblox` module::

    $ sudo neutron-db-manage upgrade head

This should be done on one of the controller nodes, assuming all controller
nodes share a common database cluster.

Modify the OpenStack Configuration
==================================
The ``neutron.conf`` files on each controller node, as well as the ``nova.conf``
files on each compute node, must be updated as described below.

Neutron
-------
The grid connectivity and credentials configuration must be added to the
``neutron.conf`` file in `infoblox` and `infoblox-dc` stanzas. The `infoblox`
stanza contains a list of grids, and then each there is an `infoblox-dc`
containing the appropriate configuration for each grid. Support for multiple
grids is not yet available.

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Option
     - Description
   * - cloud_data_center_id
     - An integer ID used for the data center. This is used to form the stanza
       name for the rest of the options.
   * - grid_master_host
     - The IP address of the Grid Master
   * - admin_user_name
     - The user name to use for the WAPI.
   * - admin_password
     - The password to use for the WAPI.
   * - wapi_version
     - The WAPI version to use. Default is 1.4. Version 2.2 or later is
       recommended, if your grid supports it (WAPI version 2.2 is supported
       in NIOS 7.2)
   * - ssl_verify
     - Set to false if you use a self-signed SSL certificate, and true
       if you use a certificate signed by a known certificate authority. You
       can also set this to a path to a certificate file so that verification
       will be done even for a self-signed certificate. Using a value of False
       in a production environment is not secure.
   * - http_pool_connections, http_pool_maxsize, http_request_timeout
     - Optional parameters to control the HTTP session pool.

Additionally, the `ipam_driver` option must be set in ``neutron.conf`` to
`infoblox`.

These settings must be done on *each controller* that runs the Neutron service.

Example (replace the ALL_CAPS values with those appropriate for your
installation):

.. code-block:: ini

   ipam_driver = infoblox

   [infoblox]
   cloud_data_center_id = 1

   [infoblox-dc:1]
   grid_master_host = GRID_MASTER_HOST
   admin_user_name = USER
   admin_password = PASSWORD
   wapi_version = 2.2

In addition to these options, you must enable the notifications options
within Neutron, if they are not already enabled.

.. code-block:: ini

   notification_driver = messagingv2
   notification_topics = notifications

Nova
----
On each controller node running the Nova service, as well as compute node
running nova-compute, you must configure Nova to send notifications.
These notifications are used by the Infoblox IPAM agent to manage DNS entries
and extensible attribute values for VMs. Set the following values in ``nova.conf``,
if they are not already set.

.. code-block:: ini

   notification_driver = messagingv2
   notification_topics = notifications
   notify_on_state_change = vm_state

Start the Infoblox IPAM Agent
=============================
Depending on your distribution, you will need to create and configure
init.d and/or systemd service definitions for the ``infoblox-ipam-agent``.
Once that is done, you should start the agent.

To start it manually, without any init.d or systemd setup, you run the
following command as the same user that runs neutron-server::

    # /usr/local/bin/infoblox-ipam-agent >/var/log/neutron/infoblox-ipam-agent.log 2>&1

Restart the Services
====================
The appropriate services must be restarted to pick up the changes to the
configuration files.

Neutron
-------
Restart ``neutron-server`` on each node running it. The exact command may vary
based upon your distribution. In Ubuntu the command is::

    $ sudo service neutron-server restart

Nova
----
If you modified the Nova notification settings, you must restart the Nova
Compute service on each node running it. The exact command may vary based
on your distribution. In Ubuntu the command is::

    $ sudo service nova-compute restart
