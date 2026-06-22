#!/bin/bash
# install dependencies
cd
cp ~/VarCHEKER/reports/*.csv ~/VarCHEKER-reports/.
cd VarCHEKER-reports
git add *.csv && git commit -m "update $(date)" && git push origin main --force
echo
echo "Updated repository."
echo "###########################################################"
