Enabling in Devstack
====================

To enable networking-infoblox in DevStack, you need to modify your ``local.conf``
prior to running ``stack.sh``. You must configure the specific properties for
your environment, as well as enable the DevStack plugin. To enable the plugin,
add this line to your ``local.conf``, replacing `master` with the branch or
release you want. (Note that stable/liberty is the 1.0.0 driver, which is
not full-featured. Later versions support Liberty and may be used instead).

 enable_plugin networking-infoblox https://git.openstack.org/openstack/networking-infoblox.git master

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
   * - grid_master_name
     - NETWORKING_INFOBLOX_DC_GRID_MASTER_NAME
   * - admin_user_name
     - NETWORKING_INFOBLOX_DC_ADMIN_USER_NAME
   * - admin_password
     - NETWORKING_INFOBLOX_DC_ADMIN_PASSWORD
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
   * - wapi_max_results
     - NETWORKING_INFOBLOX_DC_WAPI_MAX_RESULTS
   * - wapi_paging
     - NETWORKING_INFOBLOX_DC_WAPI_PAGING
   * - n/a (DevStack only)
     - NETWORKING_INFOBLOX_SUPERUSER_USERNAME
   * - n/a (DevStack only)
     - NETWORKING_INFOBLOX_SUPERUSER_PASSWORD
   * - n/a (DevStack only)
     - NETWORKING_INFOBLOX_DC_PARTICIPATING_NETWORK_VIEWS
