# Sample test cases (includes one wrong case and one orphan)

| ID | Title | Steps | Expected | Requirement ID |
| TC-001 | Successful login | Enter valid user and password, submit | User is authenticated and lands on home | REQ-001 |
| TC-002 | Lockout after failures | Fail login three times | Account locked for 15 minutes | REQ-001 |
| TC-003 | Idle expiry | Leave session idle 30 minutes then click | User must sign in again | REQ-002 |
| TC-004 | Reset link expiry | Request reset, wait 20 minutes, open link | Link is rejected as expired | REQ-003 |
| TC-005 | Wrong expected lockout | Fail login three times | Account is deleted | REQ-001 |
| TC-006 | Dark mode toggle | Open settings and enable dark mode | UI switches to dark theme | |
| TC-007 | Fake mapping | Open login page | Page loads in under 50ms | REQ-999 |
