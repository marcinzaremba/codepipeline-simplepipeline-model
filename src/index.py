import json
import os
from typing import Dict, List, Optional, Callable

import cerberus

Resources = Dict[str, Dict]

MACRO_NAME = os.environ['MACRO_NAME']
TYPE_TO_ACTION_TYPE_ID = {
    'Source::CodeCommit': {
        'Category': 'Source',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'CodeCommit',
    },
    'Source::S3': {
        'Category': 'Source',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'S3'
    },
    'Source::GitHub': {
        'Category': 'Source',
        'Owner': 'ThirdParty',
        'Version': 1,
        'Provider': 'GitHub',
    },
    'Invoke::Lambda': {
        'Category': 'Invoke',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'Lambda',
    }
}
MACRO_SCHEMA = {
    'Resources': {
        'type': 'dict',
        'valueschema': {
            'type': 'dict',
            'schema': {
                'Type': {
                    'type': 'string',
                    'required': True,
                    'oneof': [
                        {
                            'allowed': [f'{MACRO_NAME}::Pipeline'],
                            'dependencies': [
                                'Properties.Stages',
                            ],
                        }
                    ]
                },
                'Properties': {
                    'oneof': [
                        {
                            'type': 'dict',
                            'dependencies': {'Type': f'{MACRO_NAME}::Pipeline'},
                            'schema': {
                                'Stages': {
                                    'type': 'list',
                                    'required': True,
                                    'minlength': 1,
                                    'schema': {
                                        'type': 'dict',
                                        'minlength': 1,
                                        'maxlength': 1,
                                        'valueschema': {
                                            'type': 'dict',
                                            'schema': {
                                                'Type': {
                                                    'type': 'string',
                                                    'required': True,
                                                    'allowed': list(TYPE_TO_ACTION_TYPE_ID.keys()),
                                                },
                                                'Configuration': {
                                                    'type': 'dict',
                                                    'required': True,
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
}


def transform_pipeline(name: str, resource: Dict) -> Dict:
    stages = []
    for stage in resource['Properties']['Stages']:
        stage_name, value = next(iter(stage.items()))

        action_type_id = TYPE_TO_ACTION_TYPE_ID[value['Type']]
        action = {
            'Name': stage_name,
            'ActionTypeId': action_type_id,
            'Configuration': value['Configuration'],
        }
        # if action_type_id['Category'] == 'Source':
        #     action['OutputArtifacts'] = [{'Name': name}]
        # if action_type_id['Provider'] == 'Lambda':
        #     user_parameters = action.get('Configuration', {}).get('UserParameters')
        #     if user_parameters:
        #         action['Configuration']['UserParameters'] = json.dumps(user_parameters)

        stages.append({'Name': stage_name, 'Actions': [action]})

    resource['Properties']['Stages'] = stages

    return {
        name: resource
    }


TRANSFORM_FUNCTIONS = {
    f'{MACRO_NAME}::Pipeline': transform_pipeline,
}


def response(event: Dict, template: Dict, status: Optional[str] = None) -> Dict:
    return {
        'requestId': event['requestId'],
        'status': status or 'success',
        'fragment': template,
    }


def get_prefixed_resources(template: Dict, prefix: str) -> Resources:
    resources = template.get('Resources', {}) or {}
    prefixed_resources = {}
    for name, resource in resources.items():
        resource_type = resource.get('Type')
        if resource_type and resource_type.startswith(prefix):
            prefixed_resources[name] = resource

    return prefixed_resources


def transform_resources(resources: Resources, 
                        functions: Dict[str, Callable[[Dict], Dict]]) -> Resources:
    transformed_resources = {}
    for name, resource in resources.items():
        function = functions[resource['Type']]
        transformed_resources.update(function(name, resource))

    return transformed_resources


def handler(event: Dict, context) -> Dict:
    template = event['fragment']
    resources = get_prefixed_resources(template, f'{MACRO_NAME}::')
    if not resources:
        return response(event, template)

    validator = cerberus.Validator(MACRO_SCHEMA)
    validator.validate({'Resources': resources})
    if validator.errors:
        print(f'Validation errors: {validator.errors}')
        return response(event, template, 'failure')

    template['Resources'].update(transform_resources(resources, TRANSFORM_FUNCTIONS))
    print(f'Transformed template: {template}')
    
    return response(event, template)
