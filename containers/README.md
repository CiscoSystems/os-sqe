## Building and running container
* Build container with 
```sh  
$ docker build -t test_tools:latest  .
```

* Run container with: 
```sh    
$ docker run -d -P --name test_tools test_tools:latest
```

## Running tempest
* Create external network for mercury installation with subnet.
* Edit in container /tempest/etc/default-overrides.conf add values to [identity] section
     - admin_tenant_name
     - admin_password
     - admin_username
     - uri_v3
     - uri

* In container run to create config

```sh  
python tools/config_tempest.py --create
```

* Run tests with 

```sh  
 $  ostestr --regex  '(?!.*\[.*\bslow\b.*\])(^tempest\.(api|scenario))' 
```

### Pitfals


 If your subnet for external network  floating ip pool is small set --concurrency param to 2 or 1 

```sh  
 $  ostestr --regex  '(?!.*\[.*\bslow\b.*\])(^tempest\.(api|scenario))' --parallel --concurrency 1 
```
    
    
 This will help you to avoid "No more IP addresses available on network tempest" fails, but will dramatically slowdown test execution.

 If cinder is used set backup=true to [volume-feature-enabled] section to enable tests

### Changing default user\image\flavor:

set values for 

    flavor_ref 
    flavor_ref_alt 
    image_ref 
    image_ssh_user
    image_ref_alt
    image_alt_user 
    
in [compute] section of default-overrides.conf.
 
## Images
* [ubuntu](http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-i386-disk1.img)
* [cirros](http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-disk.img)


## Running cloud99
    cd /cloud99
    edit openrc 
    source openrc
    source install.sh
    rally-manage db recreate
    rally deployment create --fromenv --name=t3<deployment_name>
    rally deployment check
    
Install sshpass
