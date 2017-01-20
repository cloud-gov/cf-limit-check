#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time

import schedule
import marshmallow as ma
from webargs import fields
from awslimitchecker.checker import AwsLimitChecker
import requests

class Config(ma.Schema):
    region = fields.Str(load_from='AWS_DEFAULT_REGION', required=True)
    access_key_id = fields.Str(load_from='AWS_ACCESS_KEY_ID', required=True)
    secret_access_key = fields.Str(load_from='AWS_SECRET_ACCESS_KEY', required=True)
    services = fields.DelimitedList(fields.Str, load_from='SERVICES', required=True)
    use_ta = fields.Bool(load_from='USE_TA', missing=True)
    slack_url = fields.Str(load_from='SLACK_URL', required=True)
    slack_username = fields.Str(load_from='SLACK_USERNAME', missing='limit-check')
    slack_channel = fields.Str(load_from='SLACK_CHANNEL', required=True)
    slack_icon = fields.Str(load_from='SLACK_ICON', required=True)
    schedule_interval = fields.Int(load_from='SCHEDULE_INTERVAL', missing=60 * 24)

def check(config):
    checker = AwsLimitChecker(region=config['region'])
    warnings, errors = [], []
    for service in config['services']:
        result = checker.check_thresholds(service=service, use_ta=config['use_ta'])
        w, e = process_result(result)
        warnings.extend(w)
        errors.extend(e)

    attachments = errors + warnings
    if attachments:
        requests.post(
            config['slack_url'],
            json={
                'username': config['slack_username'],
                'channel': config['slack_channel'],
                'icon_url': config['slack_icon'],
                'text': 'AWS Quota report:',
                'attachments': attachments
            },
        ).raise_for_status()

def make_attachment(color, service, limit_name, usage, limit):
    return {
        "color": color,
        "title": "{service}: {limit_name}".format(service=service, limit_name=limit_name),
        "fields": [
            {
                "title": "Current Usage:",
                "value": usage,
                "short": True
            },
            {
                "title": "Quota Limit:",
                "value": limit,
                "short": True
            }

        ]
    }

def process_result(result):
    warnings, errors = [], []
    for service, svc_limits in result.items():
        for limit_name, limit in svc_limits.items():
            for warn in limit.get_warnings():
                warnings.append(make_attachment('warning', service, limit_name, str(warn), str(limit.get_limit())))

            for crit in limit.get_criticals():
                errors.append(make_attachment('danger', service, limit_name, str(crit), str(limit.get_limit())))

    return warnings, errors


if __name__ == "__main__":
    config = Config(strict=True).load(os.environ).data
    schedule.every(config['schedule_interval']).minutes.do(check, config)
    while True:
        schedule.run_pending()
        time.sleep(1)
