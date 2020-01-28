#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sys

import requests
import marshmallow as ma
from webargs import fields
from awslimitchecker.services import _Ec2Service
from awslimitchecker.checker import AwsLimitChecker


# todo (mxplusb): remove this in favour of something more...reasonable.
class Config(ma.Schema):
    region = fields.Str(load_from='AWS_DEFAULT_REGION', required=True)
    access_key_id = fields.Str(load_from='AWS_ACCESS_KEY_ID', required=False)
    secret_access_key = fields.Str(load_from='AWS_SECRET_ACCESS_KEY', required=False)
    services = fields.DelimitedList(fields.Str, load_from='SERVICES', required=True)
    use_ta = fields.Bool(load_from='USE_TA', missing=True)
    slack_url = fields.Str(load_from='SLACK_URL', required=True)
    slack_username = fields.Str(load_from='SLACK_USERNAME', missing='limit-check')
    slack_channel = fields.Str(load_from='SLACK_CHANNEL', required=True)
    slack_icon = fields.Str(load_from='SLACK_ICON', required=True)
    limit_overrides = fields.Str(load_from='LIMIT_OVERRIDES')

    # @ma.post_load
    # def load_overrides(self, item):
    #     overrides = json.loads(item['limit_overrides'] or '{}')
    #     ec2 = _Ec2Service(0, 1, {}, None)
    #     overrides.setdefault('EC2', {})
    #     for instance_type in ec2._instance_types():
    #         key = 'Running On-Demand {} instances'.format(instance_type)
    #         overrides['EC2'].setdefault(key, -1)
    #     item['limit_overrides'] = overrides
    #     return item


class ConfigLoader(object):
    def __init__(self):
        pass

    def _load_slack(self):
        pass

    def _load_aws(self):
        pass

    def _load_limit_overrides(self):
        pass


def check(config):
    checker = AwsLimitChecker(region=config['region'])

    overrides = json.loads(config["limit_overrides"])
    checker.set_limit_overrides(override_dict=overrides)

    warnings, errors = [], []
    result = checker.check_thresholds(service=config['services'], use_ta=config['use_ta'])
    w, e = process_result(result)
    warnings.extend(w)
    errors.extend(e)

    attachments = errors + warnings
    if attachments:
        try:
            requests.post(
                config['slack_url'],
                json={
                    'username': config['slack_username'],
                    'channel': config['slack_channel'],
                    'icon_url': config['slack_icon'],
                    'text': 'AWS Quota report:',
                    'attachments': attachments,
                },
            ).raise_for_status()
        except Exception as e:
            print(e)
        for attachment in attachments:
            print(
                f'{attachment["title"]} - Current: {attachment["fields"][0]["value"]} Quota: {attachment["fields"][1]["value"]}')
    sys.exit(len(attachments))


def make_attachment(color, service, limit_name, usage, limit):
    return {
        "color": color,
        "title": "{service}: {limit_name}".format(service=service, limit_name=limit_name),
        "fields": [
            {
                "title": "Current Usage:",
                "value": usage,
                "short": True,
            },
            {
                "title": "Quota Limit:",
                "value": limit,
                "short": True,
            },
        ],
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
    check(config)
