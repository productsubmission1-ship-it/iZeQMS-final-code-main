# izQMS Auth Testing Playbook

## Endpoints (all prefixed with `/api`)
- POST `/api/auth/login`  body `{email, password}` — returns `{user, access_token}` + sets httpOnly cookies
- POST `/api/auth/logout`
- GET  `/api/auth/me`

## Credentials (from /app/memory/test_credentials.md)
- admin@izqms.com / Admin@izQMS2026 (roles: admin, …)
- qa.head@izqms.com / QaHead@2026
- reviewer@izqms.com / Reviewer@2026
- initiator@izqms.com / Initiator@2026

## Curl tests
```
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
curl -c /tmp/c.txt -X POST $API/api/auth/login -H 'Content-Type: application/json' -d '{"email":"admin@izqms.com","password":"Admin@izQMS2026"}'
curl -b /tmp/c.txt $API/api/auth/me
curl -b /tmp/c.txt $API/api/dashboard/summary
curl -b /tmp/c.txt $API/api/records?type=DEVIATION
```

## E-Signature
- POST `/api/records/{id}/action` body `{password, reason, action}` requires re-auth via password
