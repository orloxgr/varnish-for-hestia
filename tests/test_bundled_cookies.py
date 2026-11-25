"""The installed catalogue updates descriptions and functional rules together."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'shared'))
import cookie_database
import cookie_recognition
import cookie_views


class BundledCookies(unittest.TestCase):
    def test_editor_keeps_bundled_provider_descriptions_and_profile_actions_without_fetching(self):
        with patch.object(cookie_recognition,'fetch',side_effect=AssertionError('No runtime fetch')):
            database=cookie_database.database()
            self.assertGreater(len(database['records']),2000)
            self.assertEqual(database,json.loads(cookie_database.BUNDLED.read_text(encoding='utf-8')))
            result=cookie_views.view({'owners':{}})
        entry=database['records'][0]
        editorial=json.loads((ROOT/'shared/cookie-assessments.json').read_text(encoding='utf-8'))['records'][entry['id']]
        row=next(row for row in result['cookie_policy_rows'] if row['id']=='ocd:'+entry['id'])
        self.assertEqual(row['provider'],entry['provider'])
        self.assertEqual(row['description'],editorial['description'])
        self.assertEqual(set(row['profile_actions']),{'basic','ultracache'})
        self.assertTrue(all(action['effective_action'] in ('shared','variant','private')
                            for action in row['profile_actions'].values()))


if __name__=='__main__':unittest.main()
