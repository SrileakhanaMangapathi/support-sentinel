import unittest
from unittest.mock import patch
from agent import Store
from watcher import InboxWatcher

class WatcherTests(unittest.TestCase):
 def setUp(self):
  self.store=Store(':memory:'); self.w=InboxWatcher(self.store)
 def tearDown(self): self.store.db.close()
 def test_disabled_never_calls_gmail(self):
  with patch('watcher.access_token') as token:
   self.w.tick(); token.assert_not_called()
 def test_new_mail_only_and_duplicate_skipped(self):
  self.w.configure(True)
  with patch('watcher.access_token',return_value='fake'), patch('watcher.request',return_value={'messages':[{'id':'m1'}]}) as req, patch('watcher.gmail_message',return_value={'subject':'Support Sentinel test 4'}) as mail, patch('watcher.run_agent',return_value={'state':'verified','id':'run1'}) as run:
   self.w.tick(); self.w.next_check=0; self.w.tick()
   run.assert_called_once(); mail.assert_called_once()
   self.assertIn('after%3A',req.call_args.args[0])
 def test_failure_pauses(self):
  self.w.configure(True)
  with patch('watcher.access_token',return_value='fake'), patch('watcher.request',return_value={'messages':[{'id':'m2'}]}), patch('watcher.gmail_message',return_value={'subject':'Support Sentinel test'}), patch('watcher.run_agent',return_value={'state':'needs_review','id':'run2'}):
   self.w.tick(); self.assertFalse(self.w.status()['enabled']); self.assertEqual(self.w.status()['review_message_id'],'m2')
 def test_pagination(self):
  self.w.configure(True)
  with patch('watcher.access_token',return_value='fake'), patch('watcher.request',side_effect=[{'messages':[],'nextPageToken':'next'},{'messages':[]}]) as req:
   self.w.tick(); self.assertEqual(req.call_count,2)
 def test_resume_keeps_start_time(self):
  self.w.configure(True); since=self.w.status()['since']; self.w.configure(False); self.w.configure(True)
  self.assertEqual(since,self.w.status()['since'])
 def test_nonmatching_subject_skipped(self):
  self.w.configure(True)
  with patch('watcher.access_token',return_value='fake'), patch('watcher.request',return_value={'messages':[{'id':'m3'}]}), patch('watcher.gmail_message',return_value={'subject':'Personal message'}), patch('watcher.run_agent') as run:
   self.w.tick(); run.assert_not_called()

if __name__=='__main__': unittest.main()
