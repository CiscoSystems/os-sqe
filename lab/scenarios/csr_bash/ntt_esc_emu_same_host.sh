------------------------------------------------------------------
 esc_emu.sh <number of iterations of test> <Flag to create base 
 topology> <Flag to delete base topology> (assumes 10x CRS per 
 compute node)
 July 2016, Puneet Konghot Nair (pkonghot@cisco.com)
 Copyright (c) 2016 by cisco Systems, Inc.
 All rights reserved.
 ------------------------------------------------------------------

FLAG_CREATE=${2:-0}
if [ ${FLAG_CREATE} -eq 1 ]; then
    #hp.sh
    #csr_kill.sh 80 1
    #ticker.sh 1200
    hp.sh
    csr_create2.sh -s -c -d 10 -p 10 -f 1 -l 80
    #csr_create2.sh -s -p 10 -f 1 -l 80
    hp.sh
    ticker.sh 300
    hp.sh
fi

MAX=${1:-0}
COUNT=0
while [ $COUNT -lt $MAX ]; do
    let COUNT=COUNT+1

    printf "\n\n\n============================================================="
    printf "\nSTEP ${COUNT}.1) Starting CSR kill ...\n"
    hp.sh
    csr_kill.sh 20 11
    printf "\nSTEP ${COUNT}.1) Waiting after CSR kill ...\n"
    hp.sh
    ticker.sh 20

    printf "\n---------------------------------------------------------------\n"
    printf "\nSTEP ${COUNT}.2) Starting CSR respin ...\n"
    hp.sh
    csr_create2.sh -s -p 10 -f 11 -l 20

    printf "\nSTEP ${COUNT}.2) Finished CSR respin ...\n"
    hp.sh

    printf "\nSTEP ${COUNT}.2) Waiting after CSR respin ...\n"
    ticker.sh 60
    printf "\nSTEP ${COUNT}.2) Finished waiting after CSR respin ...\n"
    hp.sh

    printf "\n\n\n============================================================="
    printf "\nSTEP ${COUNT}.3) Starting CSR kill ...\n"
    hp.sh
    csr_kill.sh 70 61
    printf "\nSTEP ${COUNT}.3) Waiting after CSR kill ...\n"
    hp.sh
    ticker.sh 20

    printf "\n---------------------------------------------------------------\n"
    printf "\nSTEP ${COUNT}.4) Starting CSR respin ...\n"
    hp.sh
    csr_create2.sh -s -p 10 -f 61 -l 70

    printf "\nSTEP ${COUNT}.4) Finished CSR respin ...\n"
    hp.sh

    printf "\nSTEP ${COUNT}.4) Waiting after CSR respin ...\n"
    ticker.sh 60
    printf "\nSTEP ${COUNT}.4) Finished waiting after CSR respin ...\n"
    hp.sh
done

FLAG_DELETE=${3:-0}
if [ ${FLAG_DELETE} -eq 1 ]; then
    csr_delete.sh 80
fi

