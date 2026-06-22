#!/bin/bash
# install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip
sudo apt-get install python3-z3
sudo apt-get install python3-sympy

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <requiremient in csv> <Python code path>"
    exit 1
fi

requirement="$1"
code_path="$2"
file="src_list.txt"

# find all python files and generate file list
echo
echo "###########################################################"
echo "Finding all python files in $code_path"
find ./$code_path -name "*.py" > $file

python3 analyzeVar.py --file $file --rtw_file $requirement
echo "Completed analysis."
#git add reports/*.csv && git commit -m "update $(date)" && git push origin main
#echo
#echo "Updated repository."
#echo "###########################################################"
