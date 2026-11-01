"""Offline checks for the explicitly approved DEV extraction override."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.gem_radar.cpk_extractor import _extraction_service, model_selection_service

class ModelRouteChecks(unittest.TestCase):
    def settings(self, **values):
        return model_selection_service.settings.model_copy(update=values)

    def test_override_is_local_and_has_no_cloud_fallback(self):
        service = _extraction_service(self.settings(app_env='dev',dev_cpk_ollama_model='qwen3:4b'))
        enabled = [(t.provider,t.model) for t in service.tiers() if t.provider]
        self.assertEqual(enabled,[('ollama','qwen3:4b')])
        self.assertEqual(service.settings.ollama_base_url,model_selection_service.settings.ollama_base_url)
        self.assertEqual(service.ollama_options,{'num_ctx':2048,'num_batch':128})

    def test_production_and_tests_ignore_dev_override(self):
        for env in ['production','live','test']:
            self.assertIs(_extraction_service(self.settings(app_env=env,dev_cpk_ollama_model='qwen3:4b')),model_selection_service)

    def test_empty_override_preserves_existing_tiers(self):
        self.assertIs(_extraction_service(self.settings(app_env='dev',dev_cpk_ollama_model='')),model_selection_service)

    def test_shared_settings_are_not_mutated(self):
        original = model_selection_service.settings.llm_primary_model
        _extraction_service(self.settings(app_env='dev',dev_cpk_ollama_model='qwen3:4b'))
        self.assertEqual(model_selection_service.settings.llm_primary_model,original)


class RequestChecks(unittest.IsolatedAsyncioTestCase):
    async def test_actual_request_uses_scoped_model_options_and_disables_thinking(self):
        settings = model_selection_service.settings.model_copy(update={
            'app_env':'dev', 'dev_cpk_ollama_model':'qwen3:4b',
            'ollama_base_url':'http://fixture.invalid',
        })
        service = _extraction_service(settings)
        bodies = []
        def respond(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200,json={'message':{'content':'{}'}})
        real_client = httpx.AsyncClient
        with patch('app.services.model_selection_service.httpx.AsyncClient',
                   side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(respond),**kwargs)):
            await service.complete(task='fixture',messages=[{'role':'user','content':'fixture'}],max_tokens=256,json_mode=True)
        self.assertEqual(len(bodies),1)
        self.assertEqual(bodies[0]['model'],'qwen3:4b')
        self.assertFalse(bodies[0]['think'])
        self.assertEqual(bodies[0]['options'],{'num_ctx':2048,'num_batch':128,'num_predict':256})

if __name__=='__main__': unittest.main()
