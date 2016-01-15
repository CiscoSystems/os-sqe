def start(context, log, args):
    import time
    import UcsSdk
    import random

    duration = args['duration']
    period = args['period']
    vlan_start = args.get('vlan-start', 3500)
    vlan_end = args.get('vlan-end', 3800)

    ip, user, password = context.ucsm_creds()

    start_time = time.time()
    while start_time + duration > time.time():
        vlan_id = random.randint(vlan_start, vlan_end)
        vlan_name = 'TEST-{0}'.format(vlan_id)
        vlan_profile_dest = 'fabric/lan/net-{0}'.format(vlan_name)

        result = 0
        try:
            handle = UcsSdk.UcsHandle()
            handle.Login(ip, user, password)

            # Create vlan profile
            handle.StartTransaction()
            vp1 = handle.GetManagedObject(None, UcsSdk.FabricLanCloud.ClassId(), {UcsSdk.FabricLanCloud.DN: 'fabric/lan'})
            vp2 = handle.AddManagedObject(
                vp1,
                UcsSdk.FabricVlan.ClassId(),
                {UcsSdk.FabricVlan.COMPRESSION_TYPE: 'included',
                     UcsSdk.FabricVlan.DN: vlan_profile_dest,
                     UcsSdk.FabricVlan.SHARING: 'none',
                     UcsSdk.FabricVlan.PUB_NW_NAME: "",
                     UcsSdk.FabricVlan.ID: str(vlan_id),
                     UcsSdk.FabricVlan.MCAST_POLICY_NAME: "",
                     UcsSdk.FabricVlan.NAME: vlan_name,
                     UcsSdk.FabricVlan.DEFAULT_NET: "no"}
            )
            handle.CompleteTransaction()

            # Delete vlan profile
            handle.StartTransaction()
            obj = handle.GetManagedObject(
                None,
                UcsSdk.FabricVlan.ClassId(),
                {UcsSdk.FabricVlan.DN: vlan_profile_dest})

            if obj:
                handle.RemoveManagedObject(obj)
            handle.CompleteTransaction()

            handle.Logout()
            result = 1
        except Exception as ex:
            print ex
        log.info('result={0} vlan_id={1}'.format(result, vlan_id))
        time.sleep(period)
