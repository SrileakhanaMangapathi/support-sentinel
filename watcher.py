"""Inbox polling, serialized with UI intakes by the local HTTP server."""
import time
from urllib.parse import urlencode
from agent import request, gmail_message, run_agent
from gmail_auth import access_token


class InboxWatcher:
    def __init__(self, store):
        self.store = store
        self.next_check = 0

    def status(self):
        return self.store.get('watcher:settings', {'enabled': False})

    def configure(self, enabled):
        state = self.status()
        if enabled and not state.get('since'):
            state['since'] = int(time.time())
        state.update(enabled=enabled, interval=60,
                     filter='in:inbox subject:"Support Sentinel test"',
                     note='Checks new matching mail while this local app is running.')
        self.store.put('watcher:settings', state)
        self.next_check = 0
        return state

    def tick(self):
        state = self.status()
        if not state.get('enabled') or time.monotonic() < self.next_check:
            return
        self.next_check = time.monotonic() + 60
        try:
            token = access_token()
            if not token:
                raise ValueError('Connect Gmail before starting the watcher.')
            params = {'q': state['filter'] + ' after:' + str(state['since']), 'maxResults': 100}
            ids = []
            for _ in range(10):
                result = request('https://gmail.googleapis.com/gmail/v1/users/me/messages?' + urlencode(params), token)
                ids.extend(m['id'] for m in result.get('messages', []))
                if not result.get('nextPageToken'):
                    break
                params['pageToken'] = result['nextPageToken']
            else:
                raise ValueError('More than 1000 matching emails; pause and narrow the inbox scope.')
            processed = 0
            for message_id in reversed(ids):
                if self.store.get('watcher:seen:' + message_id):
                    continue
                # Record an attempt before calling any provider. Failures require explicit review.
                self.store.put('watcher:seen:' + message_id, {'state': 'attempting'})
                try:
                    email = gmail_message(message_id)
                    if 'support sentinel test' not in email['subject'].lower():
                        self.store.put('watcher:seen:' + message_id, {'state': 'skipped'})
                        continue
                    record = run_agent(self.store, email, mode='live', use_ai=False)
                    self.store.put('watcher:seen:' + message_id, {'state': record['state'], 'run_id': record['id']})
                    processed += 1
                    if record['state'] != 'verified':
                        raise ValueError('An intake needs review. Inspect Recent intakes before restarting the watcher.')
                except Exception:
                    state['review_message_id'] = message_id
                    raise
            state.update(last_check=time.time(), last_processed=processed, error=None)
        except Exception as exc:
            state.update(enabled=False, last_check=time.time(), error=str(exc) if isinstance(exc, ValueError) else 'Provider check failed. Review configuration before restarting.')
        self.store.put('watcher:settings', state)
        self.next_check = time.monotonic() + 60
