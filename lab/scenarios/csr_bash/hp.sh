for f in `cat /etc/hosts | fgrep -v localhost | awk '/.* .*compute.*/ { print $2 }'` ;
do 
echo -n $f: ; 
ssh $f grep . /sys/devices/system/node/node*/hugepages/hugepages-2048kB/free_hugepages ; 
ssh $f cat /proc/meminfo | grep -E "HugePages_Total|HugePages_Free"; 
ssh $f dp | grep vtf ;
ssh $f ls -lrt /var/crash | grep -Eiv "total";
done

