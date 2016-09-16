in_iso_path=$1
out_iso_path=$2
config=$3
##############################################################################
# # Example config file
#
# hostname=i11tb3-mgmt
# api_ip=10.30.117.6/28
# api_gateway=10.30.117.1
# dns_ip=172.29.74.154
# mgmt_ip=10.123.123.222/24
# timezone=Asia/Tokyo
##############################################################################


in_mnt_path=/tmp/in-mercury-iso
out_mnt_path=/tmp/out-mercury-iso
out_kickstart_path=${out_mnt_path}/ks/build-ks.cfg

if [ -d "$in_mnt_path" ]; then
    umount $in_mnt_path
    rm -rf $in_mnt_path
fi
if [ -d "$out_mnt_path" ]; then
    rm -rf $out_mnt_path
fi

mkdir $in_mnt_path

mount -o loop $in_iso_path $in_mnt_path
cp -r $in_mnt_path $out_mnt_path

source $config

sed -i 's|raw_input(banner)||' $out_kickstart_path
sed -i 's|raw_input("{0}Enter Hostname of management node:".format("\\n" \* newline_count))|'"\"${hostname}\"|" $out_kickstart_path
sed -i 's|raw_input("{0}Enter API address of management node in CIDR format:".format("\\n" \* (newline_count+1)))|'"\"${api_ip}\"|" $out_kickstart_path
sed -i 's|raw_input("{0}Enter IP address of default gateway on API network:".format("\\n" \* (newline_count+1)))|'"\"${api_gateway}\"|" $out_kickstart_path
sed -i 's|raw_input("{0}Enter IP address of DNS Server:".format("\\n" \* (newline_count+1)))|'"\"${dns_ip}\"|" $out_kickstart_path
sed -i 's| raw_input("{0}Enter MGMT address of management node in CIDR format:".format("\\n" \* (newline_count+1)))|'"\"${mgmt_ip}\"|" $out_kickstart_path

sed -i '/auth --enableshadow --passalgo=sha512/a rootpw --iscrypted $6$.oKEqTDhB6XJjca4$V4QRX.7nUQ560rcAXjVCDgCxISZpwti.0rfnr/i24mvC1gQeyaQe0e.B/g/xq5/HdfYVEFXkYf1f72rXLfWTx0' $out_kickstart_path
sed -i 's|timezone UTC --utc|'"$timezone|" $out_kickstart_path

mkisofs -r -N -allow-leading-dots -d -J -T -o $out_iso_path $out_mnt_path