# plugin.sh - DevStack plugin.sh dispatch script networking_infoblox

function install_networking_infoblox {
    cd $DIR_INFOBLOX
    sudo python setup.py install
    sudo pip install -r requirements.txt
}

function init_networking_infoblox {
    echo "init_networking_infoblox"
    run_process networking-infoblox "/usr/local/bin/infoblox-ipam-agent --config-file=$NEUTRON_CONF --config-file=/$Q_PLUGIN_CONF_FILE"
}

function run_db_migration_for_networking_infoblox {
    $NEUTRON_BIN_DIR/neutron-db-manage --config-file $NEUTRON_CONF --config-file /$Q_PLUGIN_CONF_FILE upgrade head
}

function update_conf_option {
    local file=$1
    local section=$2
    local option=$3
    local value=$4
    local add_mode=$5

    old_val=$(iniget "$file" "$section" "$option")

    found=$(echo -n "$old_val" | sed -n -e "/$value/,/$value/p")
    if [ -z "$found" ]
    then
        if [ "$add_mode" -eq "1" ]
        then
            wc_cnt=`echo -n $old_val | wc -c`
            if [ $wc_cnt -gt 0 ]
            then
                value="${value},${old_val}"
            fi
        fi
        inicomment "$file" "$section" "$option"
        iniadd "$file" "$section" "$option" "$value"
    fi
}

function configure_networking_infoblox {
    echo_summary "Running db migration for Infoblox Networking"

    run_db_migration_for_networking_infoblox

    # Main Configurations
    iniset $NEUTRON_CONF DEFAULT ipam_driver "networking_infoblox.ipam.driver.InfobloxPool"
    iniset $NEUTRON_CONF infoblox cloud_data_center_id $NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID
    iniset $NEUTRON_CONF infoblox keystone_auth_version 'v3'
    iniset $NEUTRON_CONF infoblox keystone_auth_uri $KEYSTONE_SERVICE_URI
    iniset $NEUTRON_CONF infoblox keystone_admin_password $ADMIN_PASSWORD
    iniset $NEUTRON_CONF infoblox keystone_admin_username admin
    iniset $NEUTRON_CONF infoblox keystone_admin_tenant_name admin
    iniset $NEUTRON_CONF infoblox keystone_admin_project_name admin
    iniset $NEUTRON_CONF infoblox keystone_admin_user_domain_id default
    iniset $NEUTRON_CONF infoblox keystone_admin_project_domain_id default
    iniset $NEUTRON_CONF infoblox keystone_admin_domain_id ""
    iniset $NEUTRON_CONF infoblox cafile ${SSL_BUNDLE_FILE:-""}
    iniset $NEUTRON_CONF infoblox insecure False
    iniset $NEUTRON_CONF infoblox cert ""
    iniset $NEUTRON_CONF infoblox key ""

    # Cloud Data Center Configurations
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID grid_master_host $NETWORKING_INFOBLOX_DC_GRID_MASTER_HOST
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID grid_master_name $NETWORKING_INFOBLOX_DC_GRID_MASTER_NAME
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID admin_user_name $NETWORKING_INFOBLOX_DC_ADMIN_USER_NAME
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID admin_password $NETWORKING_INFOBLOX_DC_ADMIN_PASSWORD
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID wapi_version $NETWORKING_INFOBLOX_DC_WAPI_VERSION
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID ssl_verify $NETWORKING_INFOBLOX_DC_SSL_VERIFY
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_pool_connections $NETWORKING_INFOBLOX_DC_HTTP_POOL_CONNECTIONS
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_pool_maxsize $NETWORKING_INFOBLOX_DC_HTTP_POOL_MAXSIZE
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID http_request_timeout $NETWORKING_INFOBLOX_DC_HTTP_REQUEST_TIMEOUT
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID wapi_max_results $NETWORKING_INFOBLOX_DC_WAPI_MAX_RESULTS
    iniset $NEUTRON_CONF infoblox-dc:$NETWORKING_INFOBLOX_CLOUD_DATA_CENTER_ID wapi_paging ${NETWORKING_INFOBLOX_DC_WAPI_PAGING:-"False"}

    # Update options that are non Infoblox specific
    NOVA_CONF=/etc/nova/nova.conf
    update_conf_option $NOVA_CONF DEFAULT notification_driver messagingv2 0
    update_conf_option $NOVA_CONF DEFAULT notification_topics notifications 0
    update_conf_option $NOVA_CONF DEFAULT notify_on_state_change vm_state 0
    update_conf_option $NEUTRON_CONF DEFAULT notification_driver messagingv2 0
    update_conf_option $NEUTRON_CONF DEFAULT notification_topics notifications 0

    # Run create_ea_defs.py to create EA definitions
    if [ -z $NETWORKING_INFOBLOX_DC_PARTICIPATING_NETWORK_VIEWS ]; then
        NETWORKING_INFOBLOX_DC_PARTICIPATING_NETWORK_VIEWS=''
    fi
    create_ea_defs -s -u "$NETWORKING_INFOBLOX_SUPERUSER_USERNAME" -p "$NETWORKING_INFOBLOX_SUPERUSER_PASSWORD" -pnv "$NETWORKING_INFOBLOX_DC_PARTICIPATING_NETWORK_VIEWS"

    # Run infoblox_grid_sync to sync Infoblox Grid information
    infoblox_grid_sync --config-file=$NEUTRON_CONF --config-file=/$Q_PLUGIN_CONF_FILE
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
        if is_service_enabled networking-infoblox; then
            init_networking_infoblox
        fi
    fi

    if [[ "$1" == "unstack" ]]; then
        # uninstall networking-infoblox
        sudo pip uninstall -q -y networking-infoblox
    fi

    if [[ "$1" == "clean" ]]; then
        # Remove state and transient data
        # Remember clean.sh first calls unstack.sh
        # no-op
        :
    fi
fi
