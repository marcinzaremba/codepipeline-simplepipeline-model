import json
import os

import cerberus

MACRO_NAME = os.environ['MACRO_NAME']
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
                                                    'allowed': ['CodeCommit', 'S3', 'Lambda']
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
TYPE_TO_ACTION_TYPE_ID = {
    'CodeCommit': {
        'Category': 'Source',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'CodeCommit',
    },
    'S3': {
        'Category': 'Source',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'S3'
    },
    'Lambda': {
        'Category': 'Invoke',
        'Owner': 'AWS',
        'Version': 1,
        'Provider': 'Lambda',
    }
}


def transform_pipeline(resource):
    stages = []
    for stage in resource['Stages']:
        name, value = next(iter(stage.items()))

        action_type_id = TYPE_TO_ACTION_TYPE_ID[value['Type']]
        action = {
            'Name': name,
            'ActionTypeId': action_type_id,
            'Configuration': value['configuration'],
        }
        if action_type_id['Category'] == 'Source':
            action['OutputArtifacts'] = [{'Name': name}]
        if action_type_id['Provider'] == 'Lambda':
            user_parameters = action.get('Configuration', {}).get('UserParameters')
            if user_parameters:
                action['Configuration']['UserParameters'] = json.dumps(user_parameters)

        stages.append({'Name': name, 'Actions': [action]})

    resource['Stages'] = stages

    return resource


TRANSFORM_FUNCTIONS = {
    f'{MACRO_NAME}::Pipeline': transform_pipeline,
}

def response(event, template, status=None):
    return {
        'requestId': event['requestId'],
        'status': status or 'success',
        'fragment': template,
    }


def handler(event, context):
    template = event['fragment']
    managed_resources = {
        name: resource
        for name, resource in template.get('Resources', {}).items()
        if resource.get('Type' , '').startswith(f'{MACRO_NAME}::')
    }
    if not managed_resources:
        print('No resources')
        return response(event, template, 'failure')

    validator = cerberus.Validator(MACRO_SCHEMA)
    validator.validate({'Resources': managed_resources})
    if validator.errors:
        print(f'Validation errors: {validator.errors}')
        return response(event, template, 'failure')

    template['Resources'].update({
        name: TRANSFORM_FUNCTIONS[resource['Type']](resource)
        for name, resource in managed_resources.items()
    })
    print(f'Transformed template: {template}')
    
    return response(event, template)
