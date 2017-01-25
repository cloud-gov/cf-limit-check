#!/bin/sh

set -e

check_path=$(dirname $0)
pip install -r ${check_path}/requirements.txt
${check_path}/check.py
