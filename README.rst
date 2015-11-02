===============================
networking-infoblox
===============================

Contains Neutron drivers for integration with Infoblox grids for IPAM and DNS.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/networking-infoblox
* Source: http://git.openstack.org/cgit/openstack/networking-infoblox
* Bugs: http://bugs.launchpad.net/networking-infoblox

Features
--------

This release of the drivers supports:

* A single network view named 'default'
* IPv4 Subnet creation and deletion
* IPv4 address allocation and deallocation as a Fixed Address

Configuring Infoblox
--------------------

Infoblox must be set up with a network view named 'default'. This network view
will be used for all OpenStack IPAM.

Setting up a separate user in Infoblox for use by OpenStack is recommended.

A `Subnet ID` extensible attribute must be defined. It will be used to store
the Neutron subnet ID on each network created.

Configuring Neutron
-------------------

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
     - The WAPI version to use. Default is 1.4.
   * - ssl_verify
     - Set to false if you use a self-signed SSL certificate, and true
       otherwise. Using a self-signed certificate in a production environment
       is not secure.
   * - http_pool_connections, http_pool_maxsize, http_request_timeout
     - Optional parameters to control the HTTP session pool.

Additionally, the `ipam_driver` option must be set in ``neutron.conf`` to
`infoblox`.

Example configuration:

.. code-block:: ini

   ipam_driver = infoblox

   [infoblox]
   cloud_data_center_id = 1

   [infoblox-dc:1]
   grid_master_host = 172.23.25.175
   admin_user_name = admin
   admin_password = infoblox
   wapi_version = 1.4

Enabling in DevStack
--------------------

To enable use of Infoblox in DevStack, add this repository as a plugin::

 enable_plugin networking-infoblox https://git.openstack.org/openstack/networking-infoblox.git

You may set the configuration options above in your ``local.conf`` by using the
corresponding variables:

.. list-table::
   :header-rows: 1
   :widths: 10 90

   * - Option
     - local.conf Variable
   * - cloud_data_center_id
     - NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID
   * - grid_master_host
     - NETWORKING_INFOBLOX_DC_GRID_MASTER_HOST
   * - admin_user_name
     - NETWORKING_INFOBLOX_DC_ADMIN_USER_NAME
   * - admin_password
     - NETWORKING_INFOBLOX_DC_ADMIN_PASSWORD
   * - cloud_user_name
     - NETWORKING_INFOBLOX_DC_CLOUD_USER_NAME
   * - cloud_user_password
     - NETWORKING_INFOBLOX_DC_CLOUD_USER_PASSWORD
   * - wapi_version
     - NETWORKING_INFOBLOX_DC_WAPI_VERSION
   * - ssl_verify
     - NETWORKING_INFOBLOX_DC_SSL_VERIFY
   * - http_pool_connections
     - NETWORKING_INFOBLOX_DC_HTTP_POOL_CONNECTIONS
   * - http_pool_maxsize
     - NETWORKING_INFOBLOX_DC_HTTP_POOL_MAXSIZE
   * - http_request_timeout
     - NETWORKING_INFOBLOX_DC_HTTP_REQUEST_TIMEOUT

Limitations
-----------

* IPv6 is not supported
* Subnet update (to change allocation pools) is not supported
* Cloud Platform appliances (Cloud API) is not supported
* Only a single network view 'default' may be used
* Overlapping IP addresses is not supported even between tenants (due to the
  network view limitation).

Known issues
------------

Subnet deletion when using the ML2 plugin will delete the subnet from Neutron
but leave the subnet in Infoblox due to Neutron bug 1510653 [#]_. A patch [#]_
for this bug is available for the master branch.

.. [#] https://launchpad.net/bugs/1510653
.. [#] https://review.openstack.org/#/c/239885/

