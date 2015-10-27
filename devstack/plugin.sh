# plugin.sh - DevStack plugin.sh dispatch script networking_infoblox

function install_networking_infoblox {
    cd $DIR_INFOBLOX
    sudo python setup.py install
}

function init_networking_infoblox {
    echo "init_networking_infoblox"
}

function run_db_migration_for_networking_infoblox {
    $NEUTRON_BIN_DIR/neutron-db-manage --config-file $NEUTRON_CONF --config-file /$Q_PLUGIN_CONF_FILE upgrade head
}

function configure_networking_infoblox {
    echo_summary "Running db migration for Infoblox Networking"

    run_db_migration_for_networking_infoblox

    # Main Configurations
    iniset $NEUTRON_CONF DEFAULT ipam_driver ""
    iniset $NEUTRON_CONF infoblox network_view_scope $NETWORKING_INFOBLOX_NETWORK_VIEW_SCOPE
    iniset $NEUTRON_CONF infoblox default_network_view $NETWORKING_INFOBLOX_DEFAULT_NETWORKVIEW
    iniset $NEUTRON_CONF infoblox default_host_name_pattern $NETWORKING_INFOBLOX_DEFAULT_HOST_NAME_PATTERN
    iniset $NEUTRON_CONF infoblox default_domain_name_pattern $NETWORKING_INFOBLOX_DEFAULT_DOMAIN_NAME_PATTERN
    iniset $NEUTRON_CONF infoblox default_ns_group $NETWORKING_INFOBLOX_DEFAULT_NS_GROUP
    iniset $NEUTRON_CONF infoblox cloud_data_center_id $NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID
    iniset $NEUTRON_CONF infoblox allow_admin_network_deletion $NETWORKING_INFOBLOX_ALLOW_ADMIN_NETWORK_DELETION
    iniset $NEUTRON_CONF infoblox use_host_records_for_ip_allocation $NETWORKING_INFOBLOX_USE_RECORDS_FOR_IP_ALLOCATION
    iniset $NEUTRON_CONF infoblox bind_dns_records_to_fixed_address $NETWORKING_INFOBLOX_BIND_DNS_RECORD_TYPES
    iniset $NEUTRON_CONF infoblox unbind_dns_records_from_fixed_address $NETWORKING_INFOBLOX_UNBIND_DNS_RECORD_TYPES
    iniset $NEUTRON_CONF infoblox delete_dns_records_associated_with_fixed_address $NETWORKING_INFOBLOX_DELETE_DNS_RECORD_TYPES

    # Cloud Data Center Configurations
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID grid_master_host $NETWORKING_INFOBLOX_DC_GRID_MASTER_HOST
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID admin_user_name $NETWORKING_INFOBLOX_DC_ADMIN_USER_NAME
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID admin_password $NETWORKING_INFOBLOX_DC_ADMIN_PASSWORD
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID cloud_user_name $NETWORKING_INFOBLOX_DC_CLOUD_USER_NAME
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID cloud_user_password $NETWORKING_INFOBLOX_DC_CLOUD_USER_PASSWORD
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID wapi_version $NETWORKING_INFOBLOX_DC_WAPI_VERSION
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID ssl_verify $NETWORKING_INFOBLOX_DC_SSL_VERIFY
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_pool_connections $NETWORKING_INFOBLOX_DC_HTTP_POOL_CONNECTIONS
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_pool_maxsize $NETWORKING_INFOBLOX_DC_HTTP_POOL_MAXSIZE
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_request_timeout $NETWORKING_INFOBLOX_DC_HTTP_REQUEST_TIMEOUT
}

DIR_INFOBLOX=$DEST/networking-infoblox

# check for service enabled
if is_service_enabled networking-infoblox; then

    if [[ "$1" == "stack" && "$2" == "pre-install" ]]; then
        # Set up system services
        echo_summary "Configuring system services for Infoblox Networking"
        #install_package cowsay

    elif [[ "$1" == "stack" && "$2" == "install" ]]; then
        # Perform installation of service source
        echo_summary "Installing Infoblox Networking"
        install_networking_infoblox

    elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
        # Configure after the other layer 1 and 2 services have been configured
        echo_summary "Configuring Infoblox Networking"
        configure_networking_infoblox

    elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
        # Initialize and start the networking-infoblox service
        echo_summary "Initializing Infoblox Networking"
        init_networking_infoblox
    fi

    if [[ "$1" == "unstack" ]]; then
        # Shut down networking_infoblox services
        # no-op
        :
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi
