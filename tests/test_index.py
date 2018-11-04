import os

import pytest

MACRO_NAME = 'SimplePipelineTest'
os.environ['MACRO_NAME'] = MACRO_NAME
from src.index import handler, response, get_prefixed_resources


@pytest.mark.parametrize('given_status,expected_status', [
    pytest.param(None, 'success', id='with_empty_status'),
    pytest.param('failure', 'failure', id='with_status'),
])
def test_response(given_status, expected_status):
    given_kwargs = {
        'event': {'requestId': 'request_id'},
        'template': 'template',
        'status': given_status
    }

    assert response(**given_kwargs) == {
        'requestId': 'request_id',
        'fragment': 'template',
        'status': expected_status,
    }


@pytest.mark.parametrize('given_template,expected_resources', [
    pytest.param({}, {}, id='with_all_empty'),
    pytest.param({'Resources': None}, {}, id='with_no_resources'),
    pytest.param({'Resources': {}}, {}, id='with_empty_resources'),
    pytest.param(
        {'Resources': {
            'PrefixedResource': {
                'Type': 'prefix::resource'
            },
            'AnotherResource': {
                'Type': 'another',
            }
        }},
        {
            'PrefixedResource': {
                'Type': 'prefix::resource'
            },
        },
        id='with_prefixed_resources',
    )
])
def test_get_prefixed_resources(given_template, expected_resources):
    assert get_prefixed_resources(given_template, 'prefix::') == expected_resources


def test_transform_resources():
    pass