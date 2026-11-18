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
build_result = env['BUILD_RESULT']
publish_result = env.get('PUBLISH_RESULT')
success = build_result == 'success' and (not publish or publish_result == 'success')
superseded = publish and success and env.get('CURRENT_SOURCE') == 'false'
updated = env.get('UPDATED_TAGS', '').split()

failures = []
if not success:
    jobs_url = f"{env['GITHUB_API_URL']}/repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=30"
    try:
        request = urllib.request.Request(jobs_url, headers={'Authorization': 'Bearer ' + env['ACTIONS_TOKEN']})
        with urllib.request.urlopen(request, timeout=10) as response:
            jobs = json.load(response)['jobs']
        for job in jobs:
            if job['conclusion'] in ('success', 'skipped', None):
                continue
            name = job['name']
            if name.startswith('build-images ('):
                service = name.removeprefix('build-images (').rstrip(')').split(',', 1)[0]
                built = any(step['name'] == 'Compile and build image' and step['conclusion'] == 'success'
                            for step in job.get('steps', []))
                failures.append((service, '版本镜像上传' if publish and built else '镜像构建', job))
            elif name == 'publish-images':
                failures.append(('固定标签', '固定标签发布', job))
    except (OSError, ValueError, KeyError):
        print('::warning::Unable to read individual Rider build jobs; sending overall result.')

if superseded:
    title = 'ℹ️ Rider 固定标签更新已跳过'
    stage = '固定标签发布'
    detail = 'main 已有更新的提交，本次版本镜像已保留。'
elif success:
    title = '✅ Rider 镜像发布成功' if publish else '✅ Rider 构建验证通过'
    stage = '固定标签发布' if publish else '分支验证'
    detail = '五个镜像已推送，171 等待手动发布。' if publish else '五个镜像验证通过，未推送。'
elif publish and build_result == 'success':
    title = '❌ Rider 固定标签发布失败'
    stage = '固定标签发布'
    detail = '五个版本镜像已上传。请核对固定标签发布日志。'
elif publish and failures and all(stage == '版本镜像上传' for _, stage, _ in failures):
    title = '❌ Rider 版本镜像上传失败'
    stage = '版本镜像上传'
    detail = '请查看失败服务的上传日志。固定标签尚未更新。'
else:
    title = '❌ Rider 镜像构建失败' if publish else '❌ Rider 构建验证失败'
    stage = '镜像构建' if publish else '分支验证'
    detail = '请查看失败项的构建日志。固定标签尚未更新。' if publish else '请查看失败项的构建日志。'

now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
branch = env['SOURCE_REF'].removeprefix('refs/heads/')
branch = re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', branch)
source_repo = 'ltm0203/Knight-boss'
source_url = f"{env['GITHUB_SERVER_URL']}/{source_repo}"
sha = env['SOURCE_SHA']
lines = [f'### {title} · Knight-boss',
         '📍 阶段：' + stage,
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
if success:
    lines.append('📊 结果：5 / 5 镜像通过')
if publish and build_result == 'success' and not success:
    lines.append('📊 构建结果：5 / 5 镜像通过')
    lines.append('📦 已确认更新的固定 tag：' + ('、'.join(updated) if updated else '无'))
for service, phase, job in failures:
    lines.append(f"❗ {service} · [{phase}日志]({job['html_url']})")
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
