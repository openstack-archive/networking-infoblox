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

    # run_db_migration_for_networking_infoblox

    # Main Configurations
    iniset $NEUTRON_CONF DEFAULT ipam_driver ""
    iniset $NEUTRON_CONF infoblox cloud_data_center_id $NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID

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
