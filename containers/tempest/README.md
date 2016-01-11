### Notes
    config_tempest.py and  api_discovery.py not merged into tempest upstream yet -  https://review.openstack.org/#/c/133245/


### Running tempest
* Create external network for mercury installation with subnet.
* Edit default-overrides.conf add values to [identity] section
     - admin_tenant_name
     - admin_password
     - admin_username
     - uri_v3
     - uri

* Build container with 
```sh  
$ docker build -t tempest:proposed  .
```
* Run container with: 
```sh    
$ docker run -d -P --name tempest tempest:proposed 
```
* SSH\attach\exec to container

## Pitfals
* If your subnet for external network  floating ip pool is small set --concurrency param to 2 or 1 
   i.e:
```sh  
$  ostestr --regex  '(?!.*\[.*\bslow\b.*\])(^tempest\.(api|scenario))' --parallel --concurrency 1 
```
        This will help you to avoid "No more IP addresses available on network tempest" fails, but this will dramatically slowdown test execution 

* If cinder is used set backup=true to  [volume-feature-enabled] section to enable tests
    
* To change default user\image\flavor in [compute] section of default-overrides.conf set
    * flavor_ref 
    * flavor_ref_alt 
    * image_ref 
    * image_ssh_user
    * image_ref_alt
    * image_alt_user 
    
            Values can be obtained via openstack command on build server with appropriate credentials i.e  
            source /path/to/bootstap/openrc
            openstack flavor list
            openstack image list
    
            Note that you may need to create some of this entities.
            Image creation can be automated for cirros img and ubuntu img.
            Just change value of DEFAULT_IMAGE in the config_tempest.py before running
            docker build -t tempest:proposed .
            
            ubuntu image "http://cloud-images.ubuntu.com/trusty/current/trusty-server-cloudimg-i386-disk1.img"
            cirros image "http://download.cirros-cloud.net/0.3.1/cirros-0.3.1-x86_64-disk.img"
             
            If you plan to use non default (non cirros) image for testing - you should put value for  
            img_file  in the [scenario] section of defaults-overrides.conf
            
            If you are using ubuntu image make sure that you use flavor bigger
            than m1.nano (use m1.small at least)