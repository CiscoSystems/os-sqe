## Building and running container
* Put your cloud credentials to $REPO/tempest-ubuntu/openrc
* Build image with
```sh  
$ docker build -t tempest:ubuntu  $REPO/containers/tempest-ubuntu
```
 This process will build the image and execute predefined list of tempest tests as the last step of build.

* If you want to re-run tempestm first start the container:
```sh    
$ docker run -it --name your_name tempest:ubuntu
```
* Then run tests:

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


