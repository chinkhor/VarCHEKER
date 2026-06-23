#!/bin/bash
# install dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip
pip3 install sympy==1.14.0
pip3 install z3-solver==4.13.0.0
pip3 install pandas==2.2.2

