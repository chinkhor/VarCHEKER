#!/bin/bash

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
echo "###########################################################"
