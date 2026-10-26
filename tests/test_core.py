import json, os, sys, tempfile, threading, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from atticus_core import config, feedback, memory, models, profile, telemetry


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.prefs = {}
        self.old = (config.DIR, config._pref, config.heard)
        config.setup(self.dir, lambda k, d: self.prefs.get(k, d), lambda: [])
        os.environ.pop('ATTICUS_ASK', None)

    def tearDown(self):
        config.DIR, config._pref, config.heard = self.old
        os.environ.pop('ATTICUS_ASK', None)


class ProfileTest(Base):
    def test_add_name_context_and_file(self):
        self.assertEqual(profile.profile_add('basics', 'name: Liliam'), 'saved')
        self.assertEqual(profile.profile_add('basics', 'name: Liliam'), 'saved')   # no duplicate
        self.assertEqual(len(profile.me()['facts']), 1)
        self.assertEqual(profile.profile_name(), 'Liliam')
        self.assertIn('Name: Liliam.', profile.profile_context('hi'))
        with open(os.path.join(self.dir, 'me.json'), encoding='utf-8') as f: data = json.load(f)
        self.assertEqual(data['version'], 2)

    def test_sensitive_is_masked_and_never_learned(self):
        profile.profile_add('notes', 'bank account: DE12345678')
        self.assertEqual(profile.me()['facts'][0]['value'], '•••• 5678')
        os.environ['ATTICUS_ASK'] = '1'
        config.heard = lambda: ['my credit card is 4111']
        self.assertIn('never learned', profile.profile_add('notes', 'credit card is 4111'))

    def test_learned_needs_users_words(self):
        os.environ['ATTICUS_ASK'] = '1'
        config.heard = lambda: ['remember I live in Berlin']
        self.assertEqual(profile.profile_add('places', 'live in Berlin'), 'saved')
        self.assertIn('not saved', profile.profile_add('places', 'live in Paris'))

    def test_set_drop_forget_source(self):
        profile.profile_add('places', 'home: Berlin')
        fid = profile.me()['facts'][0]['id']
        self.assertEqual(profile.profile_set(fid, 'home: Hamburg'), 'saved')
        self.assertEqual(profile.me()['facts'][0]['value'], 'Hamburg')
        self.assertEqual(profile.profile_drop(fid), 'forgotten')
        self.assertEqual(profile.profile_drop(fid), 'not found')
        profile.profile_add('notes', 'x: y', source='learned')
        self.assertEqual(profile.profile_forget_source('learned'), 'forgotten 1')

    def test_legacy_migration_and_import(self):
        with open(os.path.join(self.dir, 'me.json'), 'w') as f: json.dump({'name': 'Ann', 'facts': ['likes tea']}, f)
        self.assertEqual({f['kind'] for f in profile.me()['facts']}, {'name', 'fact'})
        r = profile.profile_import({'contacts': {'name': 'Ann B', 'emails': [{'label': 'work', 'value': 'a@b.de'}]}, 'mail': []})
        self.assertEqual(r['counts']['contacts'], 2)
        self.assertEqual(profile.profile_import()['errors'], ['contacts', 'mail'])

    def test_category_aliases(self):
        self.assertEqual(profile.category('Work'), 'school_work')
        self.assertEqual(profile.category('???'), 'notes')


class MemoryTest(Base):
    def test_rules(self):
        self.assertEqual(memory.remember_rule('  Dad is   Robert '), 'saved')
        memory.remember_rule('dad is robert')
        self.assertEqual(memory.memory_rules(), ['Dad is Robert'])
        memory.edit_rule('Dad is Robert', 'Dad is Rob')
        memory.remember_rule('Reply in German')
        self.assertEqual(memory.forget_rules('dad'), 1)
        self.assertEqual(memory.memory_rules(), ['Reply in German'])
        self.assertIn('Reply in German', memory.memory_find('german'))
        self.assertEqual(memory.memory_find('zebra'), 'Nothing matches.')

    def test_receipt(self):
        before = memory.memory_items()
        memory.remember_rule('Use metric')
        profile.profile_add('places', 'home: Berlin')
        r = memory.memory_receipt(before)
        self.assertEqual([x['c'] for x in r], ['places', 'rules'])
        self.assertTrue(all(x['add'] for x in r))

    def test_concurrent_writes(self):
        ts = [threading.Thread(target=memory.remember_rule, args=(f'rule {i}',)) for i in range(20)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(len(memory.memory_rules()), 20)


class ModelsTest(Base):
    def test_routing(self):
        self.assertEqual(models.routing_mode(), 'balanced')
        self.assertEqual(models.main_model(), 'haiku')
        self.prefs.update(model='opus')
        self.assertEqual((models.routing_mode(), models.main_model()), ('capable', 'opus'))
        self.prefs.clear(); self.prefs.update(escalate=False)
        self.assertEqual(models.routing_mode(), 'cheapest')
        self.assertEqual(models.work_model(), 'sonnet')

    def test_server(self):
        self.assertEqual(models.server(), {})
        self.prefs.update(apiBase='http://localhost:11434', apiModel='qwen')
        env = models.server()
        self.assertEqual(env['ANTHROPIC_AUTH_TOKEN'], 'none')
        self.assertEqual(env['ANTHROPIC_DEFAULT_SONNET_MODEL'], 'qwen')

    def test_models_list(self):
        self.prefs.update(apiBase='ftp://x')
        self.assertEqual(models.models(), [])
        self.prefs.update(apiBase='https://api.example/anthropic')
        calls = []
        def fake(url, key='', timeout=4):
            calls.append(url)
            if url.endswith('/anthropic/v1/models'): raise OSError
            return ['m1']
        with mock.patch.object(models, '_models_at', fake):
            self.assertEqual(models.models(), ['m1'])
        self.assertEqual(calls, ['https://api.example/anthropic/v1/models', 'https://api.example/v1/models'])


class TelemetryTest(Base):
    def test_opt_in_only(self):
        with mock.patch.dict(os.environ, {'ATTICUS_POSTHOG_KEY': 'k'}):
            os.environ.pop('ATTICUS_DIR', None)
            self.assertFalse(telemetry.telemetry_enabled())   # default off
            self.prefs['stats'] = True
            self.assertTrue(telemetry.telemetry_enabled())
        self.assertFalse(telemetry.telemetry_enabled())       # no key, no telemetry
        with mock.patch.object(telemetry, 'posthog') as p:
            telemetry.report_error('x'); p.assert_not_called()

    def test_clean(self):
        c = telemetry.clean(r'mail a.b@c.de at C:\Users\liliam\x.txt call +49 170 1234567 https://x.de/a?q=secret')
        for leak in ('a.b@c.de', 'liliam', '1234567', 'secret'):
            self.assertNotIn(leak, c)

    def test_hooks(self):
        old = sys.excepthook, threading.excepthook
        try:
            with mock.patch.object(telemetry, 'report_error') as r:
                prev, _ = telemetry.install_exception_hooks()
                with mock.patch.object(sys, '__excepthook__'):
                    try: raise ValueError('boom')
                    except ValueError as e:
                        with mock.patch('sys.stderr'): sys.excepthook(ValueError, e, e.__traceback__)
                self.assertEqual(r.call_args.kwargs['exception'], 'ValueError')
        finally:
            sys.excepthook, threading.excepthook = old


class FeedbackTest(Base):
    def test_body_and_url(self):
        r = feedback.feedback({'text': 'Crash', 'include': True}, last_ask='open notepad')
        self.assertIn('Crash', r['body']); self.assertIn('open notepad', r['body'])
        self.assertIn('Routing: balanced', r['body'])
        self.assertTrue(r['url'].startswith(feedback.ISSUES + '?'))
        self.assertNotIn('My last ask', feedback.feedback({})['body'])


if __name__ == '__main__':
    unittest.main()
