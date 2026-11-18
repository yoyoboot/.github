import base64, datetime, hashlib, hmac, json, os, re, subprocess
from pathlib import Path
env = os.environ
if env['SOURCE_REPOSITORY'] != 'ltm0203/Knight-boss':
    raise SystemExit('Request must originate from the configured Rider repository.')
if not env.get('DISPATCH_HMAC_SECRET'):
    raise SystemExit('RIDER_DISPATCH_HMAC_SECRET is required.')
protocol = env['PROTOCOL']
if protocol not in ('yoyoboot-public-build/v4', 'yoyoboot-public-build/v5', 'yoyoboot-public-build/v6'):
    raise SystemExit('Unsupported protocol.')
ref = env['SOURCE_REF']
branch = ref.removeprefix('refs/heads/')
if not ref.startswith('refs/heads/') or subprocess.run(['git', 'check-ref-format', ref], capture_output=True).returncode != 0:
    raise SystemExit('Unsupported branch ref.')
if not re.fullmatch(r'[0-9a-f]{40}', env['SOURCE_SHA']):
    raise SystemExit('Invalid source SHA.')
if env['SOURCE_SHA'] == '0' * 40:
    raise SystemExit('Deleted branch requests are not supported.')
if env['BUILD_MODE'] not in ('validate', 'publish') or (env['BUILD_MODE'] == 'publish' and branch != 'main'):
    raise SystemExit('Publishing is only allowed on main.')
issued = datetime.datetime.strptime(env['ISSUED_AT'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc)
if abs((datetime.datetime.now(datetime.timezone.utc) - issued).total_seconds()) > 600:
    raise SystemExit('Request expired; send a fresh signed request from the private repository.')
keys = ('PROTOCOL', 'SOURCE_REPOSITORY', 'SOURCE_REF', 'SOURCE_SHA', 'BUILD_MODE', 'ISSUED_AT')
if protocol in ('yoyoboot-public-build/v4', 'yoyoboot-public-build/v5'):
    # The current Rider main and older commits still send the previous contract.
    if not re.fullmatch(r'[0-9a-f]{40}', env['SOURCE_BEFORE_SHA']):
        raise SystemExit('Invalid source SHA.')
    if not re.fullmatch(r'[1-9][0-9]*', env['SOURCE_RUN_ID']):
        raise SystemExit('Invalid source run id.')
    if env['BUILD_INTENT'] != 'image' or env['BUILD_TARGET'] != 'all':
        raise SystemExit('Rider only builds all five images.')
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', env['NONCE']):
        raise SystemExit('Invalid nonce.')
    keys = ('PROTOCOL', 'SOURCE_REPOSITORY', 'SOURCE_REF', 'SOURCE_SHA', 'SOURCE_BEFORE_SHA',
            'SOURCE_RUN_ID', 'BUILD_INTENT', 'BUILD_TARGET', 'BUILD_MODE', 'ISSUED_AT', 'NONCE')
actor = event = ''
if protocol != 'yoyoboot-public-build/v4':
    actor, event = env['SOURCE_ACTOR'], env['SOURCE_EVENT']
    if not re.fullmatch(r'[a-zA-Z0-9-]{1,39}(?:\[bot\])?', actor) or event not in ('push', 'workflow_dispatch'):
        raise SystemExit('Invalid source actor or event.')
    keys += ('SOURCE_ACTOR', 'SOURCE_EVENT')
material = ''.join(env[key] + '\n' for key in keys)
expected = base64.b64encode(hmac.new(env['DISPATCH_HMAC_SECRET'].encode(), material.encode(), hashlib.sha256).digest()).decode()
if not hmac.compare_digest(expected, env['SIGNATURE']):
    raise SystemExit('Invalid signature.')
with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
    output.write(f"source_sha={env['SOURCE_SHA']}\nsource_ref={ref}\nbuild_mode={env['BUILD_MODE']}\nsource_actor={actor}\nsource_event={event}\n")

images = json.loads(Path(__file__).with_name('images.json').read_text(encoding='utf-8'))
selected = ['all'] if env['BUILD_MODE'] == 'publish' else list(images)
with open(env['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
    output.write(f"images={json.dumps(selected)}\n")
