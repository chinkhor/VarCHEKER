#!/bin/bash
# make sure the dependencies of PCLocator are installed
# sudo apt-get update
# sudo apt-get install make
# sudo apt-get install -y python3 python3-pip
# sudo apt-get --yes --force-yes install autoconf
# sudo apt-get --yes --force-yes install default-jre
# sudo apt-get install python3-z3
# sudo apt-get install python3-sympy

dir="ua_data"
file="src_list_file"
if ! [[ -d $dir ]]; then
    mkdir $dir
fi
ua_dir="ua_app"
ua_filter="ua_filter"
# find all python files and generate file list
echo
echo "###########################################################"
echo "Finding all python files in ua_app"
find ./$ua_dir -name "*.py" > $dir/$file

python3 analyzeVar.py --path $dir --file $file --filter $ua_filter --rtw_file requirements/RTW_ua.txt --feature_map code_map/map_ua --project "ua_app"
echo "Completed analysis."
#git add reports/*.csv && git commit -m "update $(date)" && git push origin main
echo
echo "Updated repository."
echo "###########################################################"
