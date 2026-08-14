# Sample software requirements

| ID | Title | Description | Priority |
| REQ-001 | User login | The system shall authenticate users with username and password. After three failed attempts the account is locked for 15 minutes. | must |
| REQ-002 | Session timeout | Idle sessions shall expire after 30 minutes and require re-authentication. | must |
| REQ-003 | Password reset | Users shall reset passwords via a one-time email link that expires in 20 minutes. | should |
| REQ-004 | Audit log | Successful and failed logins shall be written to an append-only audit log with timestamp and IP. | must |
