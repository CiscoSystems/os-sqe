from fabric.api import task

@task
def ucsm(host='10.77.0.80', username='ucspe', password='ucspe', service_profile_name='test_profile'):
    import UcsSdk

    try:
        u = UcsSdk.UcsHandle()
        u.Login(name=host, username=username, password=password)
        org = u.GetManagedObject(inMo=None, classId=UcsSdk.OrgOrg.ClassId(), params={UcsSdk.OrgOrg.LEVEL: '0'})
        u.AddManagedObject(inMo=org, classId=UcsSdk.LsServer.ClassId(), params={UcsSdk.LsServer.NAME: service_profile_name}, modifyPresent=True)
    except Exception as ex:
        print ex
    finally:
        u.Logout()
