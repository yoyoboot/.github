import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import urllib.parse
import urllib.request

env = os.environ
webhook = env.get('NOTIFY_WEBHOOK', '')
secret = env.get('NOTIFY_SECRET', '')
if not webhook or not secret:
    print('::notice::Rider notification skipped: configure the DingTalk webhook and signing secret.')
    raise SystemExit(0)

parsed = urllib.parse.urlsplit(webhook)
if parsed.scheme != 'https' or parsed.netloc != 'oapi.dingtalk.com' or parsed.path != '/robot/send':
    print('::warning::Rider notification webhook is not a supported DingTalk robot URL.')
    raise SystemExit(1)

repo, run_id = env['GITHUB_REPOSITORY'], env['GITHUB_RUN_ID']
run_url = f"{env['GITHUB_SERVER_URL']}/{repo}/actions/runs/{run_id}"
publish = env['BUILD_MODE'] == 'publish'
result = env['BUILD_RESULT']
built = env.get('IMAGES_BUILT') == 'true'
updated = env.get('UPDATED_TAGS', '').split()
if result == 'success':
    title = '✅ Rider 镜像发布成功' if publish else '✅ Rider 构建验证通过'
    detail = '五个镜像已推送，171 等待手动发布。' if publish else '五个镜像验证通过，未推送。'
elif publish and built:
    title = '❌ Rider 镜像推送失败'
    detail = '五个镜像构建通过。请核对推送日志，等整批成功后再发布 171。'
else:
    title = '❌ Rider 镜像构建失败' if publish else '❌ Rider 构建验证失败'
    detail = '五个镜像未全部构建成功，未开始推送。' if publish else '请查看失败项的构建日志。'

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
branch = env['SOURCE_REF'].removeprefix('refs/heads/')
branch = re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', branch)
source_repo = 'ltm0203/Knight-boss'
source_url = f"{env['GITHUB_SERVER_URL']}/{source_repo}"
sha = env['SOURCE_SHA']
lines = [f'### {title} · Knight-boss',
         '📍 阶段：' + (('镜像推送' if built else '镜像构建') if publish else '分支验证'),
         f"🕒 时间：{now:%Y-%m-%d %H:%M:%S}（北京时间）",
         f'📂 源码仓库：[{source_repo}]({source_url})']
actor = env.get('SOURCE_ACTOR', '')
if actor:
    label = '推送者' if env['SOURCE_EVENT'] == 'push' else '发起人'
    profile = f"{env['GITHUB_SERVER_URL']}/"
    profile += 'apps/' + actor.removesuffix('[bot]') if actor.endswith('[bot]') else actor
    display = actor.replace('[', r'\[').replace(']', r'\]')
    lines.append(f'👤 {label}：[{display}]({profile})')
lines += [f'📦 分支：{branch}', f'📝 提交：[{sha}]({source_url}/commit/{sha})',
          f'🔗 构建日志：[GitHub Actions #{run_id}]({run_url})']
if result == 'success':
    lines.append('📊 结果：5 / 5 镜像通过')
if publish and built and result != 'success':
    lines.append('📊 构建结果：5 / 5 镜像通过')
    lines.append('📦 已确认更新的固定 tag：' + ('、'.join(updated) if updated else '无'))
if result != 'success':
    jobs_url = f"{env['GITHUB_API_URL']}/repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=30"
    try:
        request = urllib.request.Request(jobs_url, headers={'Authorization': 'Bearer ' + env['ACTIONS_TOKEN']})
        with urllib.request.urlopen(request, timeout=10) as response:
            jobs = json.load(response)['jobs']
        for job in jobs:
            if job['name'].startswith('build-images (') and job['conclusion'] not in ('success', None):
                service = job['name'].removeprefix('build-images (').rstrip(')').split(',', 1)[0]
                if service == 'all':
                    service = '镜像推送' if built else '整批构建'
                lines.append(f"❗ {service} · [{job['conclusion']} 日志]({job['html_url']})")
    except (OSError, ValueError, KeyError):
        print('::warning::Unable to read individual Rider build jobs; sending overall result.')
lines.append('🧭 说明：' + detail)

timestamp = str(int(now.timestamp() * 1000))
signature = hmac.digest(secret.encode(), (timestamp + '\n' + secret).encode(), hashlib.sha256)
suffix = urllib.parse.urlencode({'timestamp': timestamp, 'sign': base64.b64encode(signature).decode()})
uri = parsed._replace(query=f'{parsed.query}&{suffix}', fragment='').geturl()
payload = {'msgtype': 'markdown', 'markdown': {'title': title, 'text': '\n\n'.join(lines)}}
request = urllib.request.Request(uri, data=json.dumps(payload, ensure_ascii=False).encode(),
                                 headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        receipt = json.load(response)
    if receipt.get('errcode') != 0:
        raise ValueError('DingTalk rejected the message')
except (OSError, ValueError, AttributeError):
    print('::warning::Rider DingTalk notification failed. The image build result is unchanged.')
    raise SystemExit(1)
print('Rider DingTalk notification sent.')
