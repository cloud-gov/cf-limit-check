#!/bin/sh

set -e

check_path=$(dirname $0)
pip3 install -r ${check_path}/requirements.txt
${check_path}/check.py
