# Frozen Envelope & Approval Checklist

Envelope fields:
- [ ] participants
- [ ] ordered message-ID set + watermark
- [ ] attachments
- [ ] labels
- [ ] human stated intent
- [ ] envelope hash

Grant:
- [ ] thread-local
- [ ] time-boxed TTL
- [ ] scopes (read, draft, label, propose-archive)
- [ ] grantor recorded

Approval:
- [ ] approval bound to revision hash
- [ ] approval bound to envelope hash
- [ ] re-approval on envelope change

Header states:
- human-owned, agent-proposed, agent-acting, agent-blocked-needs-human, returned

Audit event fields:
- thread_id, state_version, actor, action, rationale, content_hash, timestamp
