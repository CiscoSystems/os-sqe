#/usr/bin/bash

for f in `cat /etc/hosts | fgrep -v localhost | awk '/.* .*compute.*/ { print $2 }'` ; do echo -n $f: ; ssh $f -t docker stop neutron_vtf_4990; echo ... done; done

