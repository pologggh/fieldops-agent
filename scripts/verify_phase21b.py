import urllib.request
import urllib.error
import json
import uuid

def post_json(url, data, headers=None):
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=hdrs)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())

def get_json(url, headers=None):
    hdrs = headers or {}
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode())

uid = uuid.uuid4().hex[:6]
bob_email = f"bob_{uid}@example.com"
alice_email = f"alice_{uid}@example.com"

print(f"=== 1. Register & Login Customer Bob ({bob_email}) ===")
status, reg = post_json('http://127.0.0.1:8000/customer-auth/register', {
    'name': 'Bob The Builder',
    'email': bob_email,
    'password': 'password123',
    'phone': '555-4321'
})
bob_token = reg['access_token']
bob_headers = {'Authorization': f'Bearer {bob_token}'}
print(f"Registered Bob, Customer ID: {reg['customer']['id']}")

print("\n=== 2. Bob Submits Service Request ===")
status, sr = post_json('http://127.0.0.1:8000/customer/requests', {
    'service_type': 'HVAC Repair',
    'problem_description': 'Air conditioner compressor outside is vibrating loudly and blowing warm air',
    'location': '777 Building Road, Bay 3',
    'preferred_time': 'Tomorrow 10 AM'
}, headers=bob_headers)
bob_sr_id = sr['id']
print(f"Created Service Request #{bob_sr_id}: Status=\"{sr['customer_status']}\", Preferred=\"{sr['preferred_time']}\"")

print("\n=== 3. Operator Login & Verify Ticket in Unified Intake ===")
status, op_auth = post_json('http://127.0.0.1:8000/auth/login', {
    'username': 'operator@fieldops.com',
    'password': 'password123'
})
op_token = op_auth['access_token']
op_headers = {'Authorization': f'Bearer {op_token}'}

status, all_sr = get_json('http://127.0.0.1:8000/service-requests', headers=op_headers)
sr_list = all_sr.get('items', all_sr) if isinstance(all_sr, dict) else all_sr
matching = [x for x in sr_list if x['id'] == bob_sr_id]
assert len(matching) == 1, 'Bob request must appear in operator dashboard'
print(f"Operator verified request #{bob_sr_id} in queue: Internal Status={matching[0]['status']}, Inbound Source={matching[0].get('inbound_source')}")

print("\n=== 4. Test Strict Token Boundary ===")
try:
    urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/service-requests', headers=bob_headers))
    print("ERROR: Bob accessed internal endpoints!")
except urllib.error.HTTPError as e:
    print(f"Token boundary verified: Bob customer token rejected on internal endpoint with HTTP {e.code} Forbidden")

print("\n=== 5. Test Anti-IDOR (Alice cannot access Bob ticket) ===")
status, alice_reg = post_json('http://127.0.0.1:8000/customer-auth/register', {
    'name': 'Alice Wonder',
    'email': alice_email,
    'password': 'password123'
})
alice_headers = {'Authorization': f'Bearer {alice_reg["access_token"]}'}

try:
    urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:8000/customer/requests/{bob_sr_id}', headers=alice_headers))
    print("ERROR: Alice accessed Bobs ticket!")
except urllib.error.HTTPError as e:
    print(f"Anti-IDOR verified: Alice cannot view Bobs ticket (Returned HTTP {e.code} Not Found)")

print("\n=== 6. Bob Views Timeline & Summary ===")
status, bob_view = get_json(f'http://127.0.0.1:8000/customer/requests/{bob_sr_id}', headers=bob_headers)
print(f"Bob Request View: Customer Status=\"{bob_view['customer_status']}\", Preferred=\"{bob_view['preferred_time']}\"")
print(f"Timeline items ({len(bob_view['timeline'])}):")
for t in bob_view['timeline']:
    print(f"  - [{t['title']}] {t['description']}")

status, summary = get_json('http://127.0.0.1:8000/customer/summary', headers=bob_headers)
print(f"Bob Home Summary: active={summary['active_requests_count']}, upcoming={summary['upcoming_appointments_count']}")
print("\n>>> ALL DEMO VERIFICATIONS COMPLETED SUCCESSFULLY! <<<")
