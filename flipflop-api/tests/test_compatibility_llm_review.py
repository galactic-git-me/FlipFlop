import json
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_llm_receives_only_reviewed_engineering_as_reviewed_specs(monkeypatch):
    from app.services.compatibility_llm_review import compatibility_review_input
    from app.services.model_selection_service import model_selection_service

    captured = {}

    async def complete(**kwargs):
        captured['evidence'] = json.loads(kwargs['messages'][0]['content'].split('\n\n', 1)[1])
        return SimpleNamespace(text='{"summary":"Evidence checked.","findings":[]}', model='qwen3.5:4b')

    monkeypatch.setattr(model_selection_service, 'complete', complete)
    offer = {
        'components': [
            {'role': 'cpu', 'title': 'CPU title',
             'engineering': {'reviewed': False, 'socket': 'AM5'},
             'source_observation': {'product_properties': {'CPU socket': 'AM5'}}},
            {'role': 'motherboard', 'title': 'Board title',
             'engineering': {'reviewed': True, 'socket': 'AM5', 'reviewed_by': 'operator@example.test'},
             'source_observation': {}},
        ],
        'case_choices': [],
        'compatibility': {'checks': [{'code': 'CPU_SOCKET', 'severity': 'unknown'}]},
    }

    parts = compatibility_review_input(offer)['parts']
    assert parts[0]['reviewed_specs'] == {}
    assert parts[0]['captured_product_properties'] == {'CPU socket': 'AM5'}
    assert parts[1]['reviewed_specs'] == {'socket': 'AM5'}


@pytest.mark.asyncio
async def test_llm_review_accepts_json_fenced_by_local_model(monkeypatch):
    from app.services.compatibility_llm_review import review_compatibility_evidence
    from app.services.model_selection_service import model_selection_service

    async def complete(**kwargs):
        return SimpleNamespace(text='```json\n{"summary":"Reviewed title evidence.","findings":[]}\n```',
            model='qwen3.5:4b', provider='ollama')

    monkeypatch.setattr(model_selection_service, 'complete', complete)
    result = await review_compatibility_evidence({'components':[{'role':'cpu','title':'Ryzen 5'}],
        'compatibility':{'checks':[]}})
    assert result['summary'] == 'Reviewed title evidence.'
    assert result['provider'] == 'ollama'
