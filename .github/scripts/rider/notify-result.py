import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

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
image_total = len(json.loads(Path(__file__).with_name('images.json').read_text(encoding='utf-8')))

failures = []
upload_timeouts = 0
build_steps = []
image_jobs = {}
jobs_url = f"{env['GITHUB_API_URL']}/repos/{repo}/actions/runs/{run_id}/jobs?filter=latest&per_page=30"
try:
    request = urllib.request.Request(jobs_url, headers={'Authorization': 'Bearer ' + env['ACTIONS_TOKEN']})
    with urllib.request.urlopen(request, timeout=10) as response:
        jobs = json.load(response)['jobs']
    for job in jobs:
        name = job['name']
        if name.startswith('build-images ('):
            service = name.removeprefix('build-images (').rstrip(')').split(',', 1)[0]
            steps = {step['name']: step for step in job.get('steps', [])}
            image_jobs[service] = steps
            build_step = steps.get('Compile and build image', {})
            if build_step.get('conclusion') != 'skipped' and build_step.get('started_at'):
                build_steps.append(build_step)
        if job['conclusion'] in ('success', 'skipped', None):
            continue
        if name.startswith('build-images ('):
            built = build_step.get('conclusion') == 'success'
            phase = '版本镜像上传' if publish and built else '镜像构建'
            timed_out = phase == '版本镜像上传' and steps.get('Version image upload timed out', {}).get('conclusion') == 'success'
            upload_timeouts += int(timed_out)
            outcome = '超时' if timed_out else '失败'
            failures.append((f'{service} {phase}{outcome}', phase, job['html_url']))
        elif name == 'publish-images':
            failed_tag = env.get('FAILED_TAG')
            item = f'`{failed_tag}` 更新失败' if failed_tag else '固定标签发布失败'
            failures.append((item, '固定标签发布', job['html_url']))
except (OSError, ValueError, KeyError):
    print('::warning::Unable to read Rider job details; sending overall result.')

if superseded:
    title = '⏭️ Rider 固定标签更新已跳过'
    stage = '固定标签发布'
    detail = '进入发布阶段时，main 已有更新提交。本次版本镜像保留，固定标签未更新。'
elif success:
    title = '✅ Rider 镜像发布成功' if publish else '✅ Rider 构建验证通过'
    stage = '固定标签发布' if publish else '分支验证'
    detail = '171 等待手动部署。' if publish else '分支验证完成，镜像留在构建 runner。'
elif publish and build_result == 'success':
    title = '❌ Rider 固定标签发布失败'
    stage = '固定标签发布'
    detail = '本次发布未完成，171 等待整批标签更新成功。'
elif publish and failures and all(stage == '版本镜像上传' for _, stage, _ in failures):
    title = '❌ Rider 版本镜像上传超时' if upload_timeouts == len(failures) else '❌ Rider 版本镜像上传失败'
    stage = '版本镜像上传'
    detail = '版本镜像上传未完成，固定标签尚未更新。'
else:
    title = '❌ Rider 镜像构建失败' if publish else '❌ Rider 构建验证失败'
    stage = '镜像构建' if publish else '分支验证'
    detail = '请查看失败项的构建日志。固定标签尚未更新。' if publish else '请查看失败项的构建日志。'

beijing = datetime.timezone(datetime.timedelta(hours=8))
now = datetime.datetime.now(beijing)
branch = env['SOURCE_REF'].removeprefix('refs/heads/')
branch = re.sub(r'([\\`*_{}\[\]()#+.!|<>])', r'\\\1', branch)
source_repo = 'ltm0203/Knight-boss'
source_url = f"{env['GITHUB_SERVER_URL']}/{source_repo}"
sha = env['SOURCE_SHA']
stage_label = '跳过阶段' if superseded else '失败阶段' if publish and not success else '阶段'
lines = [f'### {title} · Knight-boss',
         f'📍 {stage_label}：{stage}',
         f"🕒 通知时间：{now:%Y-%m-%d %H:%M:%S}（北京时间）"]
build_timing = '未开始' if len(image_jobs) == image_total and not build_steps else '暂无记录'
if build_steps and all(step.get('completed_at') for step in build_steps):
    try:
        started = min(datetime.datetime.fromisoformat(step['started_at']) for step in build_steps)
        finished = max(datetime.datetime.fromisoformat(step['completed_at']) for step in build_steps)
        minutes, seconds = divmod(int((finished - started).total_seconds()), 60)
    except (ValueError, TypeError):
        print('::warning::Unable to read build timing; sending overall result.')
    else:
        started = started.astimezone(beijing)
        finished = finished.astimezone(beijing)
        end_format = '%H:%M:%S' if started.date() == finished.date() else '%Y-%m-%d %H:%M:%S'
        build_timing = f'{started:%Y-%m-%d %H:%M:%S} → {finished:{end_format}}（耗时 **{minutes} 分 {seconds} 秒**）'
lines.append(f'⏱️ 构建时间：{build_timing}')
lines.append(f'📂 源码仓库：[{source_repo}]({source_url})')
actor = env.get('SOURCE_ACTOR', '')
if actor:
    label = '推送者' if env['SOURCE_EVENT'] == 'push' else '发起人'
    profile = f"{env['GITHUB_SERVER_URL']}/"
    profile += 'apps/' + actor.removesuffix('[bot]') if actor.endswith('[bot]') else actor
    display = actor.replace('[', r'\[').replace(']', r'\]')
    lines.append(f'👤 {label}：[{display}]({profile})')
lines += [f'📦 分支：{branch}', f'📝 提交：[{sha}]({source_url}/commit/{sha})',
          f"🔗 {'发布日志' if publish else '构建日志'}：[GitHub Actions #{run_id}]({run_url})"]
results = []
if build_result == 'success' or len(image_jobs) == image_total:
    built_count = image_total if build_result == 'success' else sum(
        steps.get('Compile and build image', {}).get('conclusion') == 'success' for steps in image_jobs.values())
    results.append(f'{built_count} / {image_total} 镜像构建通过')
    if publish:
        uploaded_count = image_total if build_result == 'success' else sum(
            steps.get('Push version image', {}).get('conclusion') == 'success' for steps in image_jobs.values())
        results.append(f'{uploaded_count} / {image_total} 版本镜像已上传')
if publish and build_result == 'success' and not superseded:
    results.append(f'{len(updated)} / {image_total} 固定标签已更新')
if results:
    lines.append('📊 结果：' + '，'.join(results))
if publish and not success and updated:
    lines.append('📦 已更新：' + '、'.join(f'`{tag}`' for tag in updated))
for item, phase, url in failures:
    label = '查看发布日志' if phase == '固定标签发布' else '查看任务日志'
    lines.append(f'❗ 失败项：{item}。[{label}]({url})')
if publish or not failures:
    lines.append(('🧭 跳过原因：' if superseded else '🧭 说明：') + detail)

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
